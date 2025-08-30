import pytest
import io
import tempfile
from unittest.mock import Mock, patch, MagicMock, call
from app.workers.tasks_cpu import decompose_presentation, assemble_video


class TestDecomposePresentation:
    """Test the decompose_presentation Celery task"""
    
    @pytest.fixture
    def mock_dependencies(self):
        """Mock all external dependencies"""
        mocks = {}
        
        # Mock database session
        with patch('app.workers.tasks_cpu.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mocks['db'] = mock_db
            mocks['SessionLocal'] = mock_session_local
            
            # Mock CRUD operations
            with patch('app.workers.tasks_cpu.crud') as mock_crud:
                mocks['crud'] = mock_crud
                
                # Mock MinIO service
                with patch('app.workers.tasks_cpu.minio_service') as mock_minio:
                    mocks['minio_service'] = mock_minio
                    
                    # Mock requests
                    with patch('app.workers.tasks_cpu.requests') as mock_requests:
                        mocks['requests'] = mock_requests
                        
                        # Mock Presentation (python-pptx)
                        with patch('app.workers.tasks_cpu.Presentation') as mock_prs:
                            mocks['Presentation'] = mock_prs
                            
                            # Mock Celery chord and group
                            with patch('app.workers.tasks_cpu.chord') as mock_chord, \
                                 patch('app.workers.tasks_cpu.group') as mock_group:
                                mocks['chord'] = mock_chord
                                mocks['group'] = mock_group
                                
                                yield mocks
    
    def test_decompose_presentation_success(self, mock_dependencies):
        """Test successful presentation decomposition"""
        job_id = 1
        mocks = mock_dependencies
        
        # Setup mock job
        mock_job = Mock()
        mock_job.s3_pptx_path = "/ingest/test-presentation.pptx"
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup mock presentation with slides
        mock_slide1 = Mock()
        mock_slide1.has_notes_slide = True
        mock_slide1.notes_slide.notes_text_frame.text = "This is slide 1 notes"
        
        mock_slide2 = Mock()
        mock_slide2.has_notes_slide = True
        mock_slide2.notes_slide.notes_text_frame.text = "This is slide 2 notes"
        
        mock_slide3 = Mock()
        mock_slide3.has_notes_slide = False
        
        mock_presentation = Mock()
        mock_presentation.slides = [mock_slide1, mock_slide2, mock_slide3]
        mocks['Presentation'].return_value = mock_presentation
        
        # Setup MinIO response
        mock_response = Mock()
        mock_response.read.return_value = b"fake pptx data"
        mocks['minio_service'].client.get_object.return_value = mock_response
        mocks['minio_service'].upload_file.return_value = "/presentations/notes/slide_1.txt"
        
        # Setup LibreOffice service response
        mock_libreoffice_response = Mock()
        mock_libreoffice_response.json.return_value = {
            "image_paths": [
                "/presentations/1/images/slide-01.png",
                "/presentations/1/images/slide-02.png", 
                "/presentations/1/images/slide-03.png"
            ]
        }
        mocks['requests'].post.return_value = mock_libreoffice_response
        
        # Setup Celery chord/group mocks
        mock_header = Mock()
        mocks['group'].return_value = mock_header
        mocks['chord'].return_value = Mock()
        
        # Execute task
        decompose_presentation(job_id)
        
        # Verify database operations
        mocks['crud'].get_presentation_job.assert_called_once_with(mocks['db'], job_id)
        mocks['crud'].update_job_status.assert_has_calls([
            call(mocks['db'], job_id, "processing_slides"),
            call(mocks['db'], job_id, "synthesizing_audio")
        ])
        
        # Verify MinIO operations
        mocks['minio_service'].client.get_object.assert_called_once_with("ingest", "test-presentation.pptx")
        assert mocks['minio_service'].upload_file.call_count == 3  # One for each slide
        
        # Verify LibreOffice call
        mocks['requests'].post.assert_called_once_with(
            "http://libreoffice:8100/convert",
            json={"bucket_name": "ingest", "object_name": "test-presentation.pptx"}
        )
        
        # Verify Celery chord setup
        mocks['chord'].assert_called_once()
    
    def test_decompose_presentation_job_not_found(self, mock_dependencies):
        """Test decompose_presentation when job is not found"""
        job_id = 999
        mocks = mock_dependencies
        
        mocks['crud'].get_presentation_job.return_value = None
        
        # Execute task
        decompose_presentation(job_id)
        
        # Verify only get_presentation_job was called
        mocks['crud'].get_presentation_job.assert_called_once_with(mocks['db'], job_id)
        mocks['crud'].update_job_status.assert_not_called()
    
    def test_decompose_presentation_slides_images_mismatch(self, mock_dependencies):
        """Test when number of slides doesn't match number of images"""
        job_id = 1
        mocks = mock_dependencies
        
        # Setup mock job
        mock_job = Mock()
        mock_job.s3_pptx_path = "/ingest/test-presentation.pptx"
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup presentation with 3 slides
        mock_slides = [Mock(), Mock(), Mock()]
        for slide in mock_slides:
            slide.has_notes_slide = True
            slide.notes_slide.notes_text_frame.text = "Notes"
        
        mock_presentation = Mock()
        mock_presentation.slides = mock_slides
        mocks['Presentation'].return_value = mock_presentation
        
        # Setup MinIO response
        mock_response = Mock()
        mock_response.read.return_value = b"fake pptx data"
        mocks['minio_service'].client.get_object.return_value = mock_response
        
        # Setup LibreOffice response with only 2 images (mismatch)
        mock_libreoffice_response = Mock()
        mock_libreoffice_response.json.return_value = {
            "image_paths": [
                "/presentations/1/images/slide-01.png",
                "/presentations/1/images/slide-02.png"
            ]
        }
        mocks['requests'].post.return_value = mock_libreoffice_response
        
        # Execute task
        decompose_presentation(job_id)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_any_call(mocks['db'], job_id, "failed")
    
    def test_decompose_presentation_libreoffice_error(self, mock_dependencies):
        """Test when LibreOffice service raises an error"""
        import requests
        
        job_id = 1
        mocks = mock_dependencies
        
        # Setup mock job
        mock_job = Mock()
        mock_job.s3_pptx_path = "/ingest/test-presentation.pptx"
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup presentation
        mock_presentation = Mock()
        mock_presentation.slides = [Mock()]
        mock_presentation.slides[0].has_notes_slide = True
        mock_presentation.slides[0].notes_slide.notes_text_frame.text = "Notes"
        mocks['Presentation'].return_value = mock_presentation
        
        # Setup MinIO response
        mock_response = Mock()
        mock_response.read.return_value = b"fake pptx data"
        mocks['minio_service'].client.get_object.return_value = mock_response
        
        # Setup LibreOffice to raise error
        mocks['requests'].post.side_effect = requests.HTTPError("Service unavailable")
        
        # Execute task
        decompose_presentation(job_id)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_any_call(mocks['db'], job_id, "failed")
    
    def test_decompose_presentation_slide_notes_handling(self, mock_dependencies):
        """Test proper handling of slides with and without notes"""
        job_id = 1
        mocks = mock_dependencies
        
        # Setup mock job
        mock_job = Mock()
        mock_job.s3_pptx_path = "/ingest/test-presentation.pptx"
        mocks['crud'].get_presentation_job.return_value = mock_job
        
        # Setup slides: one with notes, one without
        mock_slide_with_notes = Mock()
        mock_slide_with_notes.has_notes_slide = True
        mock_slide_with_notes.notes_slide.notes_text_frame.text = "Slide 1 notes"
        
        mock_slide_without_notes = Mock()
        mock_slide_without_notes.has_notes_slide = False
        
        mock_presentation = Mock()
        mock_presentation.slides = [mock_slide_with_notes, mock_slide_without_notes]
        mocks['Presentation'].return_value = mock_presentation
        
        # Setup MinIO and LibreOffice responses
        mock_response = Mock()
        mock_response.read.return_value = b"fake pptx data"
        mocks['minio_service'].client.get_object.return_value = mock_response
        
        mock_libreoffice_response = Mock()
        mock_libreoffice_response.json.return_value = {
            "image_paths": [
                "/presentations/1/images/slide-01.png",
                "/presentations/1/images/slide-02.png"
            ]
        }
        mocks['requests'].post.return_value = mock_libreoffice_response
        
        # Execute task
        decompose_presentation(job_id)
        
        # Verify upload_file was called twice (once for each slide)
        assert mocks['minio_service'].upload_file.call_count == 2
        
        # Check the content of uploaded notes
        upload_calls = mocks['minio_service'].upload_file.call_args_list
        
        # First slide should have notes content
        first_call_data = upload_calls[0][1]['data']
        assert first_call_data.read() == b"Slide 1 notes"
        
        # Second slide should have empty notes
        second_call_data = upload_calls[1][1]['data'] 
        assert second_call_data.read() == b""


class TestAssembleVideo:
    """Test the assemble_video Celery task"""
    
    @pytest.fixture  
    def mock_dependencies(self):
        """Mock all external dependencies for assemble_video"""
        mocks = {}
        
        with patch('app.workers.tasks_cpu.SessionLocal') as mock_session_local:
            mock_db = Mock()
            mock_session_local.return_value = mock_db
            mocks['db'] = mock_db
            
            with patch('app.workers.tasks_cpu.crud') as mock_crud:
                mocks['crud'] = mock_crud
                
                with patch('app.workers.tasks_cpu.minio_service') as mock_minio:
                    mocks['minio_service'] = mock_minio
                    
                    with patch('tempfile.TemporaryDirectory') as mock_temp:
                        temp_dir = "/tmp/test_dir"
                        mock_temp.return_value.__enter__.return_value = temp_dir
                        mocks['temp_dir'] = temp_dir
                        
                        with patch('app.workers.tasks_cpu.ImageClip') as mock_image_clip, \
                             patch('app.workers.tasks_cpu.AudioFileClip') as mock_audio_clip, \
                             patch('app.workers.tasks_cpu.concatenate_videoclips') as mock_concat, \
                             patch('os.path.getsize') as mock_getsize:
                            
                            mocks['ImageClip'] = mock_image_clip
                            mocks['AudioFileClip'] = mock_audio_clip
                            mocks['concatenate_videoclips'] = mock_concat
                            mocks['getsize'] = mock_getsize
                            
                            yield mocks
    
    def test_assemble_video_success(self, mock_dependencies):
        """Test successful video assembly"""
        job_id = 1
        results = []  # Celery chord results (not used in current implementation)
        mocks = mock_dependencies
        
        # Setup MinIO list_objects responses
        mock_image_objects = [
            Mock(object_name="1/images/slide-01.png"),
            Mock(object_name="1/images/slide-02.png"),
            Mock(object_name="1/images/slide-03.png")
        ]
        mock_audio_objects = [
            Mock(object_name="1/audio/slide_1.wav"),
            Mock(object_name="1/audio/slide_2.wav"), 
            Mock(object_name="1/audio/slide_3.wav")
        ]
        
        def list_objects_side_effect(bucket, prefix):
            if "images" in prefix:
                return mock_image_objects
            elif "audio" in prefix:
                return mock_audio_objects
            return []
        
        mocks['minio_service'].client.list_objects.side_effect = list_objects_side_effect
        mocks['minio_service'].client.fget_object.return_value = None
        
        # Setup MoviePy mocks
        mock_audio_clips = []
        mock_image_clips = []
        mock_final_clips = []
        
        for i in range(3):
            audio_clip = Mock()
            audio_clip.duration = 5.0  # 5 seconds
            mock_audio_clips.append(audio_clip)
            
            image_clip = Mock()
            image_clip.set_duration.return_value = image_clip
            image_clip.fps = 24
            mock_image_clips.append(image_clip)
            
            final_clip = Mock()
            image_clip.set_audio.return_value = final_clip
            mock_final_clips.append(final_clip)
        
        mocks['AudioFileClip'].side_effect = mock_audio_clips
        mocks['ImageClip'].side_effect = mock_image_clips
        
        # Setup final video mock
        mock_final_video = Mock()
        mocks['concatenate_videoclips'].return_value = mock_final_video
        mocks['getsize'].return_value = 1024 * 1024  # 1MB
        
        # Setup file upload mock
        mocks['minio_service'].upload_file.return_value = "/output/1.mp4"
        
        # Execute task
        assemble_video(results, job_id)
        
        # Verify database operations
        mocks['crud'].update_job_status.assert_has_calls([
            call(mocks['db'], job_id, "assembling_video"),
            call(mocks['db'], job_id, "completed", video_path="/output/1.mp4")
        ])
        
        # Verify MinIO operations
        assert mocks['minio_service'].client.list_objects.call_count == 2  # images and audio
        assert mocks['minio_service'].client.fget_object.call_count == 6  # 3 images + 3 audio files
        
        # Verify MoviePy operations
        assert len(mock_audio_clips) == 3
        assert len(mock_image_clips) == 3
        mocks['concatenate_videoclips'].assert_called_once()
        mock_final_video.write_videofile.assert_called_once()
        
        # Verify final upload
        mocks['minio_service'].upload_file.assert_called_once()
    
    def test_assemble_video_missing_audio(self, mock_dependencies):
        """Test video assembly when audio file is missing"""
        job_id = 1
        results = []
        mocks = mock_dependencies
        
        # Setup objects with missing audio for slide 2
        mock_image_objects = [
            Mock(object_name="1/images/slide-01.png"),
            Mock(object_name="1/images/slide-02.png")
        ]
        mock_audio_objects = [
            Mock(object_name="1/audio/slide_1.wav")
            # Missing slide_2.wav
        ]
        
        def list_objects_side_effect(bucket, prefix):
            if "images" in prefix:
                return mock_image_objects
            elif "audio" in prefix:
                return mock_audio_objects
            return []
        
        mocks['minio_service'].client.list_objects.side_effect = list_objects_side_effect
        
        # Execute task
        assemble_video(results, job_id)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_any_call(mocks['db'], job_id, "failed")
    
    def test_assemble_video_exception_handling(self, mock_dependencies):
        """Test video assembly exception handling"""
        job_id = 1
        results = []
        mocks = mock_dependencies
        
        # Make list_objects raise an exception
        mocks['minio_service'].client.list_objects.side_effect = Exception("MinIO error")
        
        # Execute task
        assemble_video(results, job_id)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_any_call(mocks['db'], job_id, "failed")
    
    def test_assemble_video_moviepy_error(self, mock_dependencies):
        """Test video assembly with MoviePy error"""
        job_id = 1
        results = []
        mocks = mock_dependencies
        
        # Setup successful MinIO operations
        mock_image_objects = [Mock(object_name="1/images/slide-01.png")]
        mock_audio_objects = [Mock(object_name="1/audio/slide_1.wav")]
        
        def list_objects_side_effect(bucket, prefix):
            if "images" in prefix:
                return mock_image_objects
            elif "audio" in prefix:
                return mock_audio_objects
            return []
        
        mocks['minio_service'].client.list_objects.side_effect = list_objects_side_effect
        
        # Make AudioFileClip raise an exception
        mocks['AudioFileClip'].side_effect = Exception("Audio processing error")
        
        # Execute task
        assemble_video(results, job_id)
        
        # Verify job was marked as failed
        mocks['crud'].update_job_status.assert_any_call(mocks['db'], job_id, "failed")