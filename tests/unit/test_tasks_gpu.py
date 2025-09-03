import pytest
from unittest.mock import Mock, patch, call
from celery.exceptions import SoftTimeLimitExceeded

# Mock the entire service and processor for isolation
# This avoids issues with their complex internal dependencies (like torch)
@pytest.fixture(autouse=True)
def mock_tts_processor():
    with patch('app.workers.tasks_gpu.TTSProcessor', autospec=True) as mock_processor:
        # an instance of the mock
        mock_instance = mock_processor.return_value
        mock_instance.synthesize_with_custom_voice.return_value = "temp_output.wav"
        mock_instance.synthesize_with_builtin_voice.return_value = "temp_output.wav"
        mock_instance.synthesize_base_only.return_value = "temp_output.wav"
        mock_instance.create_silence.return_value = "temp_silence.wav"
        yield mock_processor


@pytest.fixture
def mock_audio_synthesis_service():
    with patch('app.workers.tasks_gpu.audio_service', autospec=True) as mock_service:
        # Mock methods on the instance
        mock_service.load_job_data.return_value = Mock()
        mock_service.synthesize_audio.return_value = "path/to/audio.wav"
        mock_service.upload_audio_file.return_value = "s3/path/to/audio.wav"
        mock_service.cleanup_temp_files.return_value = None
        yield mock_service


# We need to import the task after the mocks are set up
# to ensure the task uses the mocked services
from app.workers.tasks_gpu import synthesize_audio, AudioSynthesisService, TTSException

# --- Unit Tests for AudioSynthesisService ---

@patch('app.workers.tasks_gpu.minio_service', autospec=True)
@patch('app.workers.tasks_gpu.TTSProcessor', autospec=True)
def test_service_load_job_data_custom_voice(mock_tts_processor, mock_minio_service):
    """Test AudioSynthesisService loads data for a custom voice clone."""
    db_session = Mock()
    mock_job = Mock()
    mock_job.s3_pptx_path = "ingest/my-job-uuid.pptx"
    mock_job.voice_clone.s3_path = "voice-clones/user/custom.wav"
    
    with patch('app.workers.tasks_gpu.crud.get_presentation_job', return_value=mock_job):
        # Mock MinIO get_object calls
        mock_voice_response = Mock()
        mock_voice_response.read.return_value = b"voice_data"
        mock_voice_response.close.return_value = None
        mock_voice_response.release_conn.return_value = None
        
        mock_note_response = Mock()
        mock_note_response.read.return_value = b"note_text"
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if bucket == "voice-clones":
                return mock_voice_response
            if bucket == "presentations":
                return mock_note_response
            raise ValueError(f"Unexpected bucket: {bucket}")

        mock_minio_service.client.get_object.side_effect = get_object_side_effect

        service = AudioSynthesisService(mock_tts_processor, mock_minio_service)
        data = service.load_job_data(db_session, 1, 1)

        assert not data.use_builtin_speaker
        assert data.reference_audio_data == b"voice_data"
        assert data.note_text == "note_text"


@patch('app.workers.tasks_gpu.minio_service', autospec=True)
@patch('app.workers.tasks_gpu.TTSProcessor', autospec=True)
def test_service_synthesize_audio_fallback_logic(mock_tts_processor, mock_minio_service):
    """Test that the service falls back from custom voice to base TTS, then to silence."""
    service = AudioSynthesisService(mock_tts_processor.return_value, mock_minio_service)
    mock_data = Mock()
    mock_data.use_builtin_speaker = False

    # Scenario 1: Custom voice fails, fallback to base TTS succeeds
    mock_tts_processor.return_value.synthesize_with_custom_voice.side_effect = TTSException("Custom failed")
    mock_tts_processor.return_value.synthesize_base_only.return_value = "base_tts.wav"

    result = service.synthesize_audio(mock_data)
    assert result == "base_tts.wav"
    mock_tts_processor.return_value.synthesize_base_only.assert_called_once()
    mock_tts_processor.return_value.create_silence.assert_not_called()

    # Reset mocks
    mock_tts_processor.return_value.synthesize_base_only.reset_mock()
    
    # Scenario 2: Both custom and base TTS fail, fallback to silence
    mock_tts_processor.return_value.synthesize_with_custom_voice.side_effect = TTSException("Custom failed again")
    mock_tts_processor.return_value.synthesize_base_only.side_effect = TTSException("Base failed too")
    mock_tts_processor.return_value.create_silence.return_value = "silence.wav"
    
    result = service.synthesize_audio(mock_data)
    assert result == "silence.wav"
    mock_tts_processor.return_value.create_silence.assert_called_once()


# --- Unit Tests for synthesize_audio Celery Task ---

@patch('app.workers.tasks_gpu.SessionLocal')
def test_task_success_flow(mock_session_local, mock_audio_synthesis_service):
    """Test the successful execution flow of the synthesize_audio task."""
    mock_db = mock_session_local.return_value
    mock_task_context = Mock()
    mock_task_context.request.id = "test_task_123"

    with patch('app.workers.tasks_gpu.crud') as mock_crud:
        # Use .s() to create a signature that can be called directly for testing
        result = synthesize_audio.s(1, 1).apply(task_id=mock_task_context.request.id).get()

        # Verify the service methods were called in order
        mock_audio_synthesis_service.load_job_data.assert_called_once_with(mock_db, 1, 1)
        mock_audio_synthesis_service.synthesize_audio.assert_called_once()
        mock_audio_synthesis_service.upload_audio_file.assert_called_once()
        mock_audio_synthesis_service.cleanup_temp_files.assert_called_once()

        # Verify task status updates
        assert mock_crud.update_task_status.call_count == 2
        
        # Final status should be 'completed'
        final_status_call = mock_crud.update_task_status.call_args_list[1]
        assert final_status_call.kwargs['status'] == 'completed'
        
        assert "Audio for slide 1 of job 1 created" in result


@patch('app.workers.tasks_gpu.SessionLocal')
def test_task_soft_time_limit_exceeded(mock_session_local, mock_audio_synthesis_service):
    """Test the task's behavior on a SoftTimeLimitExceeded exception."""
    mock_db = mock_session_local.return_value
    
    # Make the main synthesis call raise the timeout
    mock_audio_synthesis_service.synthesize_audio.side_effect = SoftTimeLimitExceeded()
    
    # Mock job data loading for the fallback path
    mock_job_data = Mock()
    mock_job_data.job = Mock()
    mock_audio_synthesis_service.load_job_data.return_value = mock_job_data
    
    with patch('app.workers.tasks_gpu.crud') as mock_crud, \
         patch('app.workers.tasks_gpu.tts_processor') as mock_global_tts_processor:
        
        result = synthesize_audio.s(1, 1).apply().get()

        # Verify that the fallback to create silence was triggered
        mock_global_tts_processor.create_silence.assert_called_once()
        
        # Verify that the fallback audio was uploaded
        mock_audio_synthesis_service.upload_audio_file.assert_called_once()
        
        # Verify the task status was updated to completed with a timeout message
        final_status_call = mock_crud.update_task_status.call_args_list[1]
        assert final_status_call.kwargs['status'] == 'completed'
        assert "timed out" in final_status_call.kwargs['progress_message']
        
        assert "Timeout fallback audio" in result


@patch('app.workers.tasks_gpu.SessionLocal')
def test_task_general_exception(mock_session_local, mock_audio_synthesis_service):
    """Test the task's behavior on a generic exception."""
    mock_db = mock_session_local.return_value

    # Make data loading fail
    error_message = "Database connection failed"
    mock_audio_synthesis_service.load_job_data.side_effect = Exception(error_message)

    with pytest.raises(Exception, match=error_message), \
         patch('app.workers.tasks_gpu.crud') as mock_crud:
        
        synthesize_audio.s(1, 1).apply().get()

        # Verify that the task and job statuses were updated to 'failed'
        mock_crud.update_task_status.assert_called_once_with(
            mock_db,
            celery_task_id=synthesize_audio.request.id,
            status='failed',
            error_message=error_message
        )
        mock_crud.update_job_status.assert_called_once_with(
            mock_db,
            1,
            'failed',
            error_message=f"Audio synthesis failed for slide 1: {error_message}"
        )