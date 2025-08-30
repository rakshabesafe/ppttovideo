import pytest
import io
import time
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient


class TestFullWorkflow:
    """Integration tests for the complete presentation processing workflow"""
    
    @pytest.fixture
    def complete_setup(self, client, db_session, sample_user_data):
        """Setup complete environment for workflow testing"""
        # Create user
        user_response = client.post("/api/users/", json=sample_user_data)
        user_id = user_response.json()["id"]
        
        # Create voice clone
        with patch('app.api.endpoints.voice_clones.minio_service') as mock_minio:
            mock_minio.upload_file.return_value = "/voice-clones/test-voice.wav"
            wav_data = b"RIFF" + b"\x00" * 44
            
            voice_response = client.post(
                "/api/voice-clones/",
                data={"name": "Test Voice", "owner_id": user_id},
                files={"file": ("test.wav", io.BytesIO(wav_data), "audio/wav")}
            )
        
        voice_clone_id = voice_response.json()["id"]
        
        return {
            "user_id": user_id,
            "voice_clone_id": voice_clone_id,
            "user_data": sample_user_data
        }
    
    @patch('app.api.endpoints.presentations.celery_app')
    @patch('app.api.endpoints.presentations.minio_service')
    def test_complete_presentation_workflow(self, mock_minio, mock_celery, client, complete_setup):
        """Test the complete workflow from upload to completion"""
        setup = complete_setup
        
        # Mock MinIO and Celery
        mock_minio.upload_file.return_value = "/ingest/test-presentation.pptx"
        mock_celery.send_task.return_value = None
        
        # Step 1: Upload presentation
        pptx_data = b"PK" + b"\x00" * 100  # Minimal PPTX-like data
        response = client.post(
            "/api/presentations/",
            data={
                "owner_id": setup["user_id"], 
                "voice_clone_id": setup["voice_clone_id"]
            },
            files={"file": ("test.pptx", io.BytesIO(pptx_data),
                          "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
        
        assert response.status_code == 200
        job_data = response.json()
        job_id = job_data["id"]
        
        # Verify initial job state
        assert job_data["status"] == "pending"
        assert job_data["owner_id"] == setup["user_id"]
        assert job_data["voice_clone_id"] == setup["voice_clone_id"]
        
        # Step 2: Check job status
        status_response = client.get(f"/api/presentations/status/{job_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "pending"
        
        # Step 3: Verify task was dispatched
        mock_celery.send_task.assert_called_once()
        task_name, task_args = mock_celery.send_task.call_args[0]
        assert "decompose_presentation" in task_name
        assert task_args == [job_id]
        
        # Step 4: Simulate job progression (would be done by Celery workers)
        # This tests the database update functionality
        from app import crud
        
        # Simulate processing stages
        updated_job = crud.update_job_status(client.app.dependency_overrides[client.app.router.dependencies[0]](), 
                                           job_id, "processing_slides")
        assert updated_job.status == "processing_slides"
        
        updated_job = crud.update_job_status(client.app.dependency_overrides[client.app.router.dependencies[0]](),
                                           job_id, "synthesizing_audio") 
        assert updated_job.status == "synthesizing_audio"
        
        updated_job = crud.update_job_status(client.app.dependency_overrides[client.app.router.dependencies[0]](),
                                           job_id, "assembling_video")
        assert updated_job.status == "assembling_video"
        
        updated_job = crud.update_job_status(client.app.dependency_overrides[client.app.router.dependencies[0]](),
                                           job_id, "completed", "/output/video.mp4")
        assert updated_job.status == "completed"
        assert updated_job.s3_video_path == "/output/video.mp4"
        
        # Step 5: Verify final status
        final_status = client.get(f"/api/presentations/status/{job_id}")
        assert final_status.status_code == 200
        final_data = final_status.json()
        assert final_data["status"] == "completed"
        assert final_data["s3_video_path"] == "/output/video.mp4"
    
    def test_multiple_users_workflow(self, client, db_session):
        """Test workflow with multiple users"""
        # Create two users
        user1_data = {"name": "User 1", "email": "user1@example.com"}
        user2_data = {"name": "User 2", "email": "user2@example.com"}
        
        user1_response = client.post("/api/users/", json=user1_data)
        user2_response = client.post("/api/users/", json=user2_data)
        
        user1_id = user1_response.json()["id"]
        user2_id = user2_response.json()["id"]
        
        # Create voice clones for each user
        with patch('app.api.endpoints.voice_clones.minio_service') as mock_minio:
            mock_minio.upload_file.side_effect = [
                "/voice-clones/user1-voice.wav",
                "/voice-clones/user2-voice.wav"
            ]
            wav_data = b"RIFF" + b"\x00" * 44
            
            voice1_response = client.post(
                "/api/voice-clones/",
                data={"name": "User 1 Voice", "owner_id": user1_id},
                files={"file": ("voice1.wav", io.BytesIO(wav_data), "audio/wav")}
            )
            
            voice2_response = client.post(
                "/api/voice-clones/",
                data={"name": "User 2 Voice", "owner_id": user2_id},
                files={"file": ("voice2.wav", io.BytesIO(wav_data), "audio/wav")}
            )
        
        voice1_id = voice1_response.json()["id"]
        voice2_id = voice2_response.json()["id"]
        
        # Create presentations for each user
        with patch('app.api.endpoints.presentations.celery_app') as mock_celery, \
             patch('app.api.endpoints.presentations.minio_service') as mock_minio:
            
            mock_minio.upload_file.side_effect = [
                "/ingest/user1-presentation.pptx",
                "/ingest/user2-presentation.pptx"
            ]
            mock_celery.send_task.return_value = None
            
            pptx_data = b"PK" + b"\x00" * 100
            
            job1_response = client.post(
                "/api/presentations/",
                data={"owner_id": user1_id, "voice_clone_id": voice1_id},
                files={"file": ("pres1.pptx", io.BytesIO(pptx_data),
                              "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
            )
            
            job2_response = client.post(
                "/api/presentations/",
                data={"owner_id": user2_id, "voice_clone_id": voice2_id},
                files={"file": ("pres2.pptx", io.BytesIO(pptx_data),
                              "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
            )
        
        # Verify both jobs were created correctly
        assert job1_response.status_code == 200
        assert job2_response.status_code == 200
        
        job1_data = job1_response.json()
        job2_data = job2_response.json()
        
        assert job1_data["owner_id"] == user1_id
        assert job2_data["owner_id"] == user2_id
        
        # Verify jobs are isolated per user
        all_jobs_response = client.get("/api/presentations/status/all")
        all_jobs = all_jobs_response.json()
        
        user1_jobs = [job for job in all_jobs if job["owner_id"] == user1_id]
        user2_jobs = [job for job in all_jobs if job["owner_id"] == user2_id]
        
        assert len(user1_jobs) == 1
        assert len(user2_jobs) == 1
        assert user1_jobs[0]["id"] == job1_data["id"]
        assert user2_jobs[0]["id"] == job2_data["id"]
    
    def test_error_handling_workflow(self, client, complete_setup):
        """Test workflow error handling"""
        setup = complete_setup
        
        # Test invalid file type
        invalid_response = client.post(
            "/api/presentations/",
            data={"owner_id": setup["user_id"], "voice_clone_id": setup["voice_clone_id"]},
            files={"file": ("test.txt", io.BytesIO(b"text"), "text/plain")}
        )
        
        assert invalid_response.status_code == 400
        assert "Invalid file type" in invalid_response.json()["detail"]
        
        # Test non-existent voice clone
        invalid_voice_response = client.post(
            "/api/presentations/",
            data={"owner_id": setup["user_id"], "voice_clone_id": 99999},
            files={"file": ("test.pptx", io.BytesIO(b"PK" + b"\x00" * 100),
                          "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
        )
        
        # This should fail at the database level due to foreign key constraint
        assert invalid_voice_response.status_code in [400, 422, 500]
    
    def test_concurrent_job_processing(self, client, complete_setup):
        """Test handling of multiple concurrent jobs"""
        setup = complete_setup
        
        with patch('app.api.endpoints.presentations.celery_app') as mock_celery, \
             patch('app.api.endpoints.presentations.minio_service') as mock_minio:
            
            mock_celery.send_task.return_value = None
            mock_minio.upload_file.side_effect = [
                f"/ingest/presentation-{i}.pptx" for i in range(5)
            ]
            
            # Create multiple jobs quickly
            pptx_data = b"PK" + b"\x00" * 100
            job_responses = []
            
            for i in range(5):
                response = client.post(
                    "/api/presentations/",
                    data={"owner_id": setup["user_id"], "voice_clone_id": setup["voice_clone_id"]},
                    files={"file": (f"test{i}.pptx", io.BytesIO(pptx_data),
                                  "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
                )
                job_responses.append(response)
            
            # Verify all jobs were created successfully
            assert all(resp.status_code == 200 for resp in job_responses)
            
            job_ids = [resp.json()["id"] for resp in job_responses]
            assert len(set(job_ids)) == 5  # All jobs have unique IDs
            
            # Verify all tasks were dispatched
            assert mock_celery.send_task.call_count == 5
    
    def test_data_consistency(self, client, complete_setup):
        """Test data consistency across the workflow"""
        setup = complete_setup
        
        with patch('app.api.endpoints.presentations.celery_app') as mock_celery, \
             patch('app.api.endpoints.presentations.minio_service') as mock_minio:
            
            mock_minio.upload_file.return_value = "/ingest/test-presentation.pptx"
            mock_celery.send_task.return_value = None
            
            # Create presentation job
            pptx_data = b"PK" + b"\x00" * 100
            create_response = client.post(
                "/api/presentations/",
                data={"owner_id": setup["user_id"], "voice_clone_id": setup["voice_clone_id"]},
                files={"file": ("test.pptx", io.BytesIO(pptx_data),
                              "application/vnd.openxmlformats-officedocument.presentationml.presentation")}
            )
            
            job_id = create_response.json()["id"]
            
            # Verify data relationships
            job_status_response = client.get(f"/api/presentations/status/{job_id}")
            job_data = job_status_response.json()
            
            # Verify foreign key relationships
            user_response = client.get(f"/api/users/{job_data['owner_id']}")
            assert user_response.status_code == 200
            assert user_response.json()["id"] == setup["user_id"]
            
            voice_response = client.get(f"/api/voice-clones/user/{setup['user_id']}")
            voice_clones = voice_response.json()
            matching_voice = next(vc for vc in voice_clones if vc["id"] == job_data["voice_clone_id"])
            assert matching_voice["owner_id"] == setup["user_id"]
            
            # Verify job appears in all jobs list
            all_jobs_response = client.get("/api/presentations/status/all")
            all_jobs = all_jobs_response.json()
            matching_job = next(job for job in all_jobs if job["id"] == job_id)
            assert matching_job["owner_id"] == setup["user_id"]
            assert matching_job["voice_clone_id"] == setup["voice_clone_id"]