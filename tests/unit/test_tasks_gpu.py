import pytest
import io
import tempfile
from unittest.mock import Mock, patch, MagicMock
import torch
from app.workers.tasks_gpu import synthesize_audio


class TestSynthesizeAudio:
    """Test the synthesize_audio Celery task"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies"""
        mocks = {}
        
        with patch('app.workers.tasks_gpu.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mocks['db'] = mock_db
            
            with patch('app.workers.tasks_gpu.crud') as mock_crud:
                mocks['crud'] = mock_crud
                
                with patch('app.workers.tasks_gpu.minio_service') as mock_minio:
                    mocks['minio_service'] = mock_minio
                    
                    with patch('app.workers.tasks_gpu.se_extractor') as mock_se_extractor, \
                         patch('app.workers.tasks_gpu.tone_color_converter') as mock_converter, \
                         patch('app.workers.tasks_gpu.librosa') as mock_librosa, \
                         patch('app.workers.tasks_gpu.torch') as mock_torch, \
                         patch('builtins.open') as mock_open:
                        
                        mocks['se_extractor'] = mock_se_extractor  
                        mocks['tone_color_converter'] = mock_converter
                        mocks['librosa'] = mock_librosa
                        mocks['torch'] = mock_torch
                        mocks['open'] = mock_open
                        
                        # Setup librosa mocks
                        mock_librosa.load.return_value = (torch.zeros(24000).numpy(), 24000)
                        mock_librosa.effects.trim.return_value = (torch.zeros(20000).numpy(), None)
                        mock_librosa.output.write_wav.return_value = None
                        
                        # Setup torch mocks
                        mock_torch.zeros.return_value = torch.zeros(24000)
                        
                        yield mocks
    
    def test_synthesize_audio_success(self, mock_dependencies):
        """Test successful audio synthesis"""
        job_id = 1
        slide_number = 1
        mocks = mock_dependencies
        
        # Setup mock job with voice clone
        mock_voice_clone = Mock()
        mock_voice_clone.s3_path = "/voice-clones/user1/voice.wav"
        
        mock_job = Mock()
        mock_job.voice_clone = mock_voice_clone
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup MinIO responses
        # Voice clone audio
        mock_ref_response = Mock()
        mock_ref_response.read.return_value = b"fake audio data"
        mock_ref_response.close.return_value = None
        mock_ref_response.release_conn.return_value = None
        
        # Note text
        mock_note_response = Mock() 
        mock_note_response.read.return_value = b"This is slide 1 content"
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if "voice.wav" in object_name:
                return mock_ref_response
            elif "notes" in object_name:
                return mock_note_response
            return Mock()
        
        mocks['minio_service'].client.get_object.side_effect = get_object_side_effect
        mocks['minio_service'].upload_file.return_value = "/presentations/1/audio/slide_1.wav"
        
        # Setup OpenVoice mocks
        mock_target_se = torch.zeros(256)
        mocks['se_extractor'].get_se.return_value = (mock_target_se, "audio_name")
        mocks['tone_color_converter'].convert.return_value = None
        
        # Setup file operations
        mock_file_handle = Mock()
        mocks['open'].return_value.__enter__.return_value = mock_file_handle
        
        # Execute task
        result = synthesize_audio(job_id, slide_number)
        
        # Verify database operations
        mocks['crud'].get_presentation_job.assert_called_once_with(mocks['db'], job_id)
        
        # Verify MinIO operations
        assert mocks['minio_service'].client.get_object.call_count == 2  # voice + notes
        mocks['minio_service'].upload_file.assert_called_once()
        
        # Verify audio processing
        mocks['librosa'].load.assert_called_once()
        mocks['librosa'].effects.trim.assert_called_once()
        mocks['se_extractor'].get_se.assert_called_once()
        mocks['tone_color_converter'].convert.assert_called_once()
        
        # Verify return value
        assert "Audio for slide 1 of job 1 created" in result
    
    def test_synthesize_audio_job_not_found(self, mock_dependencies):
        """Test audio synthesis when job is not found"""
        job_id = 999
        slide_number = 1
        mocks = mock_dependencies
        
        mocks['crud'].get_presentation_job.return_value = None
        
        # Execute task and expect exception
        with pytest.raises(Exception) as exc_info:
            synthesize_audio(job_id, slide_number)
        
        assert "Job 999 not found" in str(exc_info.value)
        mocks['crud'].update_job_status.assert_not_called()
    
    def test_synthesize_audio_empty_notes(self, mock_dependencies):
        """Test audio synthesis with empty notes (silence)"""
        job_id = 1
        slide_number = 2
        mocks = mock_dependencies
        
        # Setup mock job
        mock_voice_clone = Mock()
        mock_voice_clone.s3_path = "/voice-clones/user1/voice.wav"
        mock_job = Mock()
        mock_job.voice_clone = mock_voice_clone
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup MinIO responses - empty notes
        mock_ref_response = Mock()
        mock_ref_response.read.return_value = b"fake audio data"
        mock_ref_response.close.return_value = None
        mock_ref_response.release_conn.return_value = None
        
        mock_note_response = Mock()
        mock_note_response.read.return_value = b"   "  # Only whitespace
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if "voice.wav" in object_name:
                return mock_ref_response
            elif "notes" in object_name:
                return mock_note_response
            return Mock()
        
        mocks['minio_service'].client.get_object.side_effect = get_object_side_effect
        mocks['minio_service'].upload_file.return_value = "/presentations/1/audio/slide_2.wav"
        
        # Setup file operations
        mock_file_handle = Mock()
        mocks['open'].return_value.__enter__.return_value = mock_file_handle
        
        # Execute task
        result = synthesize_audio(job_id, slide_number)
        
        # Verify that silence handling was triggered
        # Should create silent audio instead of using TTS
        mocks['librosa'].output.write_wav.assert_called()
        
        # Should not call tone_color_converter for silence
        mocks['tone_color_converter'].convert.assert_not_called()
        
        assert "Audio for slide 2 of job 1 created" in result
    
    def test_synthesize_audio_with_silence_tag(self, mock_dependencies):
        """Test audio synthesis with [SILENCE] tag"""
        job_id = 1
        slide_number = 3
        mocks = mock_dependencies
        
        # Setup mock job
        mock_voice_clone = Mock()
        mock_voice_clone.s3_path = "/voice-clones/user1/voice.wav"
        mock_job = Mock()
        mock_job.voice_clone = mock_voice_clone
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup MinIO responses - silence tag
        mock_ref_response = Mock()
        mock_ref_response.read.return_value = b"fake audio data"
        mock_ref_response.close.return_value = None
        mock_ref_response.release_conn.return_value = None
        
        mock_note_response = Mock()
        mock_note_response.read.return_value = b"[SILENCE]"
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if "voice.wav" in object_name:
                return mock_ref_response
            elif "notes" in object_name:
                return mock_note_response
            return Mock()
        
        mocks['minio_service'].client.get_object.side_effect = get_object_side_effect
        mocks['minio_service'].upload_file.return_value = "/presentations/1/audio/slide_3.wav"
        
        # Execute task
        result = synthesize_audio(job_id, slide_number)
        
        # Verify silence was created
        mocks['torch'].zeros.assert_called_with(24000)  # 1 second of silence at 24kHz
        mocks['librosa'].output.write_wav.assert_called()
        
        # Should not process reference audio or use TTS for silence
        mocks['tone_color_converter'].convert.assert_not_called()
        
        assert "Audio for slide 3 of job 1 created" in result
    
    def test_synthesize_audio_minio_error(self, mock_dependencies):
        """Test audio synthesis with MinIO error"""
        from minio.error import S3Error
        
        job_id = 1
        slide_number = 1
        mocks = mock_dependencies
        
        # Setup mock job
        mock_job = Mock()
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Make MinIO raise error
        mocks['minio_service'].client.get_object.side_effect = S3Error(
            "NoSuchKey",
            "The specified key does not exist",
            resource="voice.wav",
            request_id="123",
            host_id="456"
        )
        
        # Execute task and expect exception
        with pytest.raises(S3Error):
            synthesize_audio(job_id, slide_number)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_called_with(mocks['db'], job_id, "failed")
    
    def test_synthesize_audio_openvoice_error(self, mock_dependencies):
        """Test audio synthesis with OpenVoice processing error"""
        job_id = 1
        slide_number = 1
        mocks = mock_dependencies
        
        # Setup mock job
        mock_voice_clone = Mock()
        mock_voice_clone.s3_path = "/voice-clones/user1/voice.wav"
        mock_job = Mock()
        mock_job.voice_clone = mock_voice_clone
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup MinIO responses
        mock_ref_response = Mock()
        mock_ref_response.read.return_value = b"fake audio data"
        mock_ref_response.close.return_value = None
        mock_ref_response.release_conn.return_value = None
        
        mock_note_response = Mock()
        mock_note_response.read.return_value = b"Test content"
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if "voice.wav" in object_name:
                return mock_ref_response
            elif "notes" in object_name:
                return mock_note_response
            return Mock()
        
        mocks['minio_service'].client.get_object.side_effect = get_object_side_effect
        
        # Make se_extractor raise error
        mocks['se_extractor'].get_se.side_effect = Exception("OpenVoice processing error")
        
        # Execute task and expect exception
        with pytest.raises(Exception):
            synthesize_audio(job_id, slide_number)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_called_with(mocks['db'], job_id, "failed")
    
    def test_synthesize_audio_file_upload_error(self, mock_dependencies):
        """Test audio synthesis with file upload error"""
        job_id = 1
        slide_number = 1
        mocks = mock_dependencies
        
        # Setup successful processing until upload
        mock_voice_clone = Mock()
        mock_voice_clone.s3_path = "/voice-clones/user1/voice.wav"
        mock_job = Mock()
        mock_job.voice_clone = mock_voice_clone
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup MinIO responses
        mock_ref_response = Mock()
        mock_ref_response.read.return_value = b"fake audio data"
        mock_ref_response.close.return_value = None
        mock_ref_response.release_conn.return_value = None
        
        mock_note_response = Mock()
        mock_note_response.read.return_value = b"Test content"
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if "voice.wav" in object_name:
                return mock_ref_response
            elif "notes" in object_name:
                return mock_note_response
            return Mock()
        
        mocks['minio_service'].client.get_object.side_effect = get_object_side_effect
        
        # Setup OpenVoice mocks
        mock_target_se = torch.zeros(256)
        mocks['se_extractor'].get_se.return_value = (mock_target_se, "audio_name")
        
        # Make file upload fail
        mocks['minio_service'].upload_file.side_effect = Exception("Upload failed")
        
        # Execute task and expect exception
        with pytest.raises(Exception):
            synthesize_audio(job_id, slide_number)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_called_with(mocks['db'], job_id, "failed")
    
    @patch('os.path.getsize')
    def test_synthesize_audio_file_operations(self, mock_getsize, mock_dependencies):
        """Test file operations during audio synthesis"""
        mock_getsize.return_value = 1024  # 1KB file
        
        job_id = 1
        slide_number = 1
        mocks = mock_dependencies
        
        # Setup successful scenario
        mock_voice_clone = Mock()
        mock_voice_clone.s3_path = "/voice-clones/user1/voice.wav"
        mock_job = Mock()
        mock_job.voice_clone = mock_voice_clone
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup MinIO responses
        mock_ref_response = Mock()
        mock_ref_response.read.return_value = b"fake audio data"
        mock_ref_response.close.return_value = None
        mock_ref_response.release_conn.return_value = None
        
        mock_note_response = Mock()
        mock_note_response.read.return_value = b"Test content"
        mock_note_response.close.return_value = None
        mock_note_response.release_conn.return_value = None
        
        def get_object_side_effect(bucket, object_name):
            if "voice.wav" in object_name:
                return mock_ref_response
            elif "notes" in object_name:
                return mock_note_response
            return Mock()
        
        mocks['minio_service'].client.get_object.side_effect = get_object_side_effect
        mocks['minio_service'].upload_file.return_value = "/presentations/1/audio/slide_1.wav"
        
        # Setup OpenVoice mocks
        mock_target_se = torch.zeros(256)
        mocks['se_extractor'].get_se.return_value = (mock_target_se, "audio_name")
        
        # Execute task
        result = synthesize_audio(job_id, slide_number)
        
        # Verify file operations
        # Should open files for writing reference audio and reading for upload
        assert mocks['open'].call_count >= 2  # At least temp files + upload file
        
        # Verify getsize was called for upload
        mock_getsize.assert_called()
        
        assert "created" in result