from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import base64
import uuid
from datetime import datetime
import os
from dotenv import load_dotenv
import json
from PIL import Image
import io
import requests

# Register HEIF support for iPhone images
try:
    import pillow_heif
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIF_AVAILABLE = True
    print("HEIF support enabled for iPhone images")
except ImportError:
    HEIF_AVAILABLE = False
    print("pillow-heif not available - HEIC images from iPhones may not work")
except Exception as e:
    HEIF_AVAILABLE = False
    print(f"Error registering HEIF support: {e}")

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Add request logging
@app.before_request
def log_request_info():
    print(f"[REQUEST] {request.method} {request.path} from {request.remote_addr}")
    if request.is_json:
        print(f"[REQUEST] Content-Type: {request.content_type}")
        print(f"[REQUEST] JSON keys: {list(request.get_json().keys()) if request.get_json() else 'None'}")
    else:
        print(f"[REQUEST] Content-Type: {request.content_type}")
        print(f"[REQUEST] Form data: {list(request.form.keys()) if request.form else 'None'}")

# AWS clients
rekognition = boto3.client('rekognition')
s3 = boto3.client('s3')
dynamodb = boto3.resource('dynamodb')
bedrock = boto3.client('bedrock-runtime')

# Configuration
BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'alzheimer-camera-faces')
COLLECTION_ID = os.getenv('REKOGNITION_COLLECTION_ID', 'alzheimer-faces')
TABLE_NAME = os.getenv('DYNAMODB_TABLE_NAME', 'alzheimer-persons')
ELEVENLABS_API_KEY = os.getenv('ELEVEN_LAB_API_KEY')
ELEVENLABS_VOICE_ID = os.getenv('VOICE_ID')
TEST_MODE = os.getenv('TEST_MODE', 'false').lower() == 'true'

# DynamoDB table
table = dynamodb.Table(TABLE_NAME)

@app.route('/recognize', methods=['POST'])
def recognize_face():
    print(f"[RECOGNIZE] Request received from {request.remote_addr}")
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Decode and convert image
        try:
            if ',' in image_data:
                image_bytes = base64.b64decode(image_data.split(',')[1])
            else:
                image_bytes = base64.b64decode(image_data)
            
            # Convert to JPEG for Rekognition
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode in ('RGBA', 'P'):
                image = image.convert('RGB')
            
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG')
            image_bytes = buffer.getvalue()
            print(f"[RECOGNIZE] Converted image size: {len(image_bytes)} bytes")
        except Exception as e:
            print(f"[RECOGNIZE] Image conversion failed: {e}")
            return jsonify({'error': f'Image conversion failed: {str(e)}'}), 400
        
        # Search for face in collection
        try:
            print(f"[RECOGNIZE] Searching in collection: {COLLECTION_ID}")
            response = rekognition.search_faces_by_image(
                CollectionId=COLLECTION_ID,
                Image={'Bytes': image_bytes},
                MaxFaces=1,
                FaceMatchThreshold=70
            )
            
            print(f"[RECOGNIZE] Rekognition response: {len(response.get('FaceMatches', []))} matches found")
            
            if response['FaceMatches']:
                match = response['FaceMatches'][0]
                person_id = match['Face']['ExternalImageId']
                confidence = match['Similarity']
                print(f"[RECOGNIZE] Match found: person_id={person_id}, confidence={confidence}%")
                
                # Get person info from DynamoDB
                db_response = table.get_item(Key={'person_id': person_id})
                person_info = db_response.get('Item', {})
                print(f"[RECOGNIZE] Person info: {person_info.get('name', 'Unknown')}")
                
                # Create structured announcement with name, role, and age
                name = person_info.get('name', 'Unknown person')
                relationship = person_info.get('relationship', 'Unknown role')
                age = person_info.get('age', 'Unknown age')
                
                # Create announcement text
                announcement = f"This is {name}, your {relationship}, age {age}."
                print(f"[RECOGNIZE] Generated announcement: {announcement}")
                
                # Generate TTS audio using ElevenLabs
                print(f"[TTS] Generating audio for person: {name}")
                audio_base64 = generate_tts_audio(announcement)
                print(f"[TTS] Audio generated: {bool(audio_base64)}, length: {len(audio_base64) if audio_base64 else 0}")
                
                result = {
                    'matched': True,
                    'person': {'name': name},
                    'note': announcement,
                    'notes': person_info.get('notes', ''),
                    'confidence': confidence
                }
                
                # Add audio if TTS was successful
                if audio_base64:
                    result['audio'] = audio_base64
                
                print(f"[RECOGNIZE] Returning result with audio: {bool(audio_base64)}")
                return jsonify(result)
            else:
                print("[RECOGNIZE] No matches found")
                return jsonify({
                    'matched': False,
                    'note': 'Person not recognized'
                })
        
        except rekognition.exceptions.InvalidParameterException as e:
            print(f"[RECOGNIZE] Invalid parameter: {e}")
            return jsonify({'error': 'No face detected in image'}), 400
        except Exception as rekognition_error:
            print(f"[RECOGNIZE] Rekognition error: {rekognition_error}")
            return jsonify({'error': f'Face recognition failed: {str(rekognition_error)}'}), 500
            
    except Exception as e:
        print(f"[RECOGNIZE] General error: {str(e)}")
        return jsonify({'error': str(e)}), 500

def generate_bedrock_note(person_info):
    """Generate human-like note using Amazon Bedrock"""
    try:
        name = person_info.get('name', 'Unknown')
        relationship = person_info.get('relationship', 'Unknown')
        age = person_info.get('age', 'Unknown')
        notes = person_info.get('notes', '')
        
        prompt = f"""Convert this information into a natural spoken reminder for someone with Alzheimer's:
        
        Person: {name} ({relationship}, age {age})
        Notes: {notes}
        
        Create a factual, conversational message that reflects the exact sentiment and information from the notes. Keep it under 50 words and suitable for audio playback."""
        
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 100,
                "temperature": 0.7
            }
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId="amazon.titan-text-lite-v1",
            accept="application/json",
            contentType="application/json"
        )
        
        response_body = json.loads(response.get('body').read())
        return response_body.get('results', [{}])[0].get('outputText', '').strip()
    except Exception as e:
        return f"This is {name}, your {relationship}. They care about you very much."

def generate_tts_audio(text):
    """Generate TTS audio using ElevenLabs and return as base64"""
    try:
        if not ELEVENLABS_API_KEY or not ELEVENLABS_VOICE_ID:
            print("ElevenLabs API key or Voice ID not configured")
            return None
        
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": ELEVENLABS_API_KEY
        }
        
        data = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.7,
                "similarity_boost": 0.5,
                "speed": 0.8
            }
        }
        
        print(f"[TTS] Generating audio for: {text[:50]}...")
        print(f"[TTS] Using API key: {ELEVENLABS_API_KEY[:10]}...")
        print(f"[TTS] Using voice ID: {ELEVENLABS_VOICE_ID}")
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            audio_base64 = base64.b64encode(response.content).decode('utf-8')
            print(f"[TTS] Audio generated successfully, size: {len(response.content)} bytes")
            return audio_base64
        else:
            print(f"[TTS] API error: {response.status_code}, response: {response.text}")
            return None
            
    except Exception as e:
        print(f"[TTS] Error: {str(e)}")
        return None

@app.route('/add_person', methods=['POST'])
def add_person():
    print(f"[ADD_PERSON] Request received from {request.remote_addr}")
    try:
        data = request.get_json()
        if not data:
            print("[ADD_PERSON] No JSON data received")
            return jsonify({'error': 'No data provided'}), 400
            
        image_data = data.get('image')
        name = data.get('name')
        relationship = data.get('relationship')
        age = data.get('age')
        notes = data.get('notes', '')
        
        print(f"[ADD_PERSON] Received - name: '{name}', relationship: '{relationship}', age: {age}")
        print(f"[ADD_PERSON] Image data length: {len(image_data) if image_data else 0}")
        
        if not image_data or not name or not relationship:
            print(f"Validation failed - image_data: {bool(image_data)}, name: '{name}', relationship: '{relationship}'")
            return jsonify({'error': 'Image, name, and relationship required'}), 400
        
        # Decode and convert image
        try:
            print(f"[ADD_PERSON] Processing image data...")
            if ',' in image_data:
                image_bytes = base64.b64decode(image_data.split(',')[1])
            else:
                image_bytes = base64.b64decode(image_data)
            
            print(f"[ADD_PERSON] Decoded image bytes: {len(image_bytes)}")
            print(f"[ADD_PERSON] First 20 bytes: {image_bytes[:20]}")
            
            # Try to open and convert image
            try:
                # Check if it's a HEIC file and handle specially
                if len(image_bytes) > 20 and b'ftyp' in image_bytes[:20] and b'heic' in image_bytes[:20]:
                    print("[ADD_PERSON] Detected HEIC image, using pillow_heif")
                    if HEIF_AVAILABLE:
                        try:
                            heif_file = pillow_heif.open_heif(io.BytesIO(image_bytes))
                            image = heif_file.to_pillow()
                        except Exception as heif_error:
                            print(f"[ADD_PERSON] HEIF processing failed: {heif_error}")
                            return jsonify({'error': 'Failed to process HEIC image'}), 400
                    else:
                        return jsonify({'error': 'HEIC images not supported on this server'}), 400
                else:
                    # Regular image processing
                    print(f"[ADD_PERSON] Processing as regular image")
                    image = Image.open(io.BytesIO(image_bytes))
                    print(f"[ADD_PERSON] Image opened successfully: {image.size}, mode: {image.mode}")
                
                # Convert to RGB if needed
                if image.mode in ('RGBA', 'P', 'L'):
                    print(f"[ADD_PERSON] Converting from {image.mode} to RGB")
                    image = image.convert('RGB')
                
                # Save as JPEG
                buffer = io.BytesIO()
                image.save(buffer, format='JPEG', quality=85)
                image_bytes = buffer.getvalue()
                print(f"[ADD_PERSON] Converted image size: {len(image_bytes)} bytes")
            except Exception as img_error:
                print(f"[ADD_PERSON] Image processing failed: {img_error}")
                print(f"[ADD_PERSON] Image error type: {type(img_error)}")
                return jsonify({'error': f'Image processing failed: {str(img_error)}'}), 400
        except Exception as e:
            print(f"[ADD_PERSON] Base64 decode error: {str(e)}")
            return jsonify({'error': f'Image decode failed: {str(e)}'}), 400
        
        # Check if person already exists
        try:
            search_response = rekognition.search_faces_by_image(
                CollectionId=COLLECTION_ID,
                Image={'Bytes': image_bytes},
                MaxFaces=1,
                FaceMatchThreshold=70
            )
            
            if search_response['FaceMatches']:
                # Person exists - update their info
                existing_person_id = search_response['FaceMatches'][0]['Face']['ExternalImageId']
                
                # Update DynamoDB with new info
                table.update_item(
                    Key={'person_id': existing_person_id},
                    UpdateExpression='SET #n = :name, relationship = :rel, age = :age, notes = :notes, updated_at = :updated',
                    ExpressionAttributeNames={'#n': 'name'},
                    ExpressionAttributeValues={
                        ':name': name,
                        ':rel': relationship,
                        ':age': age,
                        ':notes': notes,
                        ':updated': datetime.utcnow().isoformat()
                    }
                )
                
                # Add new image to existing person's S3 folder
                new_face_id = str(uuid.uuid4())
                s3_key = f"{existing_person_id}/{new_face_id}.jpg"
                s3.put_object(
                    Bucket=BUCKET_NAME,
                    Key=s3_key,
                    Body=image_bytes,
                    ContentType='image/jpeg'
                )
                
                return jsonify({
                    'success': True,
                    'person_id': existing_person_id,
                    'updated': True,
                    'message': 'Person info updated with new photo'
                })
        except:
            pass  # Person doesn't exist, create new
        
        # Create new person
        person_id = str(uuid.uuid4())
        
        # Add face to Rekognition collection (or skip in test mode)
        if TEST_MODE:
            print("[TEST_MODE] Skipping Rekognition face detection")
            face_id = str(uuid.uuid4())
        else:
            try:
                response = rekognition.index_faces(
                    CollectionId=COLLECTION_ID,
                    Image={'Bytes': image_bytes},
                    ExternalImageId=person_id,
                    MaxFaces=1
                )
                
                if not response['FaceRecords']:
                    return jsonify({
                        'error': 'No face detected in image. Please ensure:\n• The photo clearly shows a person\'s face\n• The face is well-lit and not blurry\n• The person is looking towards the camera',
                        'code': 'NO_FACE_DETECTED'
                    }), 400
                    
                face_id = response['FaceRecords'][0]['Face']['FaceId']
            except Exception as rekognition_error:
                print(f"[ADD_PERSON] Rekognition error: {rekognition_error}")
                return jsonify({'error': f'Face detection failed: {str(rekognition_error)}'}), 500
        
        # Store image in S3
        s3_key = f"{person_id}/{face_id}.jpg"
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_bytes,
            ContentType='image/jpeg'
        )
        print(f"[ADD_PERSON] Image stored in S3: {s3_key}")
        
        # Store person info in DynamoDB
        table.put_item(
            Item={
                'person_id': person_id,
                'name': name,
                'relationship': relationship,
                'age': age,
                'notes': notes,
                'face_id': face_id,
                's3_key': s3_key,
                'created_at': datetime.utcnow().isoformat()
            }
        )
        print(f"[ADD_PERSON] Person stored in DynamoDB")
        
        return jsonify({
            'success': True,
            'person_id': person_id,
            'face_id': face_id,
            'created': True,
            'message': f'Successfully added {name}!'
        })
            
    except Exception as e:
        print(f"Add person error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/reminders', methods=['GET'])
def get_reminders():
    """Get all people as reminders"""
    print(f"[REMINDERS] Request from {request.remote_addr}")
    try:
        print(f"[REMINDERS] Scanning table: {TABLE_NAME}")
        response = table.scan()
        people = response.get('Items', [])
        print(f"[REMINDERS] Found {len(people)} people")
        
        reminders = []
        for person in people:
            # Generate presigned URL for the image
            image_url = None
            if person.get('s3_key'):
                try:
                    # Check if object exists first
                    s3.head_object(Bucket=BUCKET_NAME, Key=person.get('s3_key'))
                    image_url = s3.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': BUCKET_NAME, 'Key': person.get('s3_key')},
                        ExpiresIn=3600  # 1 hour
                    )
                except Exception as e:
                    print(f"[REMINDERS] Image not found for {person.get('name')}: {e}")
                    image_url = None
            
            reminders.append({
                'person_id': person.get('person_id'),
                'name': person.get('name'),
                'relationship': person.get('relationship'),
                'age': person.get('age'),
                'notes': person.get('notes'),
                'added_date': person.get('created_at'),
                'image_url': image_url
            })
        
        print(f"[REMINDERS] Returning {len(reminders)} reminders")
        return jsonify({'reminders': reminders})
    except Exception as e:
        print(f"[REMINDERS] Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/person/<person_id>', methods=['GET'])
def get_person_details(person_id):
    """Get detailed information for a specific person"""
    try:
        # Get person info from DynamoDB
        db_response = table.get_item(Key={'person_id': person_id})
        person_info = db_response.get('Item')
        
        if not person_info:
            return jsonify({'error': 'Person not found'}), 404
        
        # Generate presigned URL for main image
        image_url = None
        if person_info.get('s3_key'):
            try:
                image_url = s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': BUCKET_NAME, 'Key': person_info.get('s3_key')},
                    ExpiresIn=3600
                )
            except Exception as e:
                print(f"Error generating presigned URL: {e}")
        
        return jsonify({
            'person_id': person_info.get('person_id'),
            'name': person_info.get('name'),
            'relationship': person_info.get('relationship'),
            'age': person_info.get('age'),
            'notes': person_info.get('notes'),
            'created_at': person_info.get('created_at'),
            'image_url': image_url
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/edit_person/<person_id>', methods=['PUT'])
def edit_person(person_id):
    """Edit a person's information and optionally add gallery images"""
    try:
        data = request.get_json()
        name = data.get('name')
        relationship = data.get('relationship')
        age = data.get('age')
        notes = data.get('notes', '')
        images = data.get('images', [])
        
        if not name or not relationship:
            return jsonify({'error': 'Name and relationship required'}), 400
        
        # Update DynamoDB
        table.update_item(
            Key={'person_id': person_id},
            UpdateExpression='SET #n = :name, relationship = :rel, age = :age, notes = :notes, updated_at = :updated',
            ExpressionAttributeNames={'#n': 'name'},
            ExpressionAttributeValues={
                ':name': name,
                ':rel': relationship,
                ':age': age,
                ':notes': notes,
                ':updated': datetime.utcnow().isoformat()
            }
        )
        
        # Handle gallery images if provided
        uploaded_media = []
        if images:
            for image_data in images:
                # Generate unique filename first
                media_id = str(uuid.uuid4())
                
                try:
                    # Decode image
                    if ',' in image_data:
                        image_bytes = base64.b64decode(image_data.split(',')[1])
                    else:
                        image_bytes = base64.b64decode(image_data)
                    
                    print(f"Gallery image data length: {len(image_bytes)} bytes")
                    print(f"First 20 bytes: {image_bytes[:20]}")
                    
                    # Check if it's a HEIC file and handle specially
                    if b'ftyp' in image_bytes[:20] and b'heic' in image_bytes[:20]:
                        print("Detected HEIC image, using pillow_heif")
                        if HEIF_AVAILABLE:
                            try:
                                heif_file = pillow_heif.open_heif(io.BytesIO(image_bytes))
                                image = heif_file.to_pillow()
                            except Exception as heif_error:
                                print(f"HEIF processing failed: {heif_error}")
                                continue
                        else:
                            print("HEIF support not available, skipping image")
                            continue
                    else:
                        # Regular image processing
                        image = Image.open(io.BytesIO(image_bytes))
                    
                    # Convert to RGB if needed
                    if image.mode in ('RGBA', 'P', 'L'):
                        image = image.convert('RGB')
                    
                    buffer = io.BytesIO()
                    image.save(buffer, format='JPEG', quality=85)
                    image_bytes = buffer.getvalue()
                    
                    # Upload to S3
                    s3_key = f"{person_id}/{media_id}.jpg"
                    s3.put_object(
                        Bucket=BUCKET_NAME,
                        Key=s3_key,
                        Body=image_bytes,
                        ContentType='image/jpeg'
                    )
                    
                    uploaded_media.append(media_id)
                    
                except Exception as e:
                    print(f"Error processing image: {e}")
                    continue
        
        response = {
            'success': True, 
            'message': 'Person updated successfully'
        }
        
        if uploaded_media:
            response['images_uploaded'] = len(uploaded_media)
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/person/<person_id>/media', methods=['GET'])
def get_person_media(person_id):
    """Get all media/images for a specific person"""
    try:
        # List all objects in the person's S3 folder
        response = s3.list_objects_v2(
            Bucket=BUCKET_NAME,
            Prefix=f"{person_id}/"
        )
        
        media = []
        for obj in response.get('Contents', []):
            # Generate presigned URL for each image
            image_url = s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': BUCKET_NAME, 'Key': obj['Key']},
                ExpiresIn=3600
            )
            
            # Extract filename for ID
            filename = obj['Key'].split('/')[-1].split('.')[0]
            
            media.append({
                'id': filename,
                'type': 'image',
                'uri': image_url,
                'thumb': image_url  # Same URL for thumb
            })
        
        return jsonify({'media': media})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/person/<person_id>/media', methods=['POST'])
def add_person_media(person_id):
    """Add new media/image to a person's gallery"""
    try:
        data = request.get_json()
        image_data = data.get('image')
        
        if not image_data:
            return jsonify({'error': 'No image provided'}), 400
        
        # Decode image
        if ',' in image_data:
            image_bytes = base64.b64decode(image_data.split(',')[1])
        else:
            image_bytes = base64.b64decode(image_data)
        
        # Convert to JPEG
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG')
        image_bytes = buffer.getvalue()
        
        # Generate unique filename
        media_id = str(uuid.uuid4())
        s3_key = f"{person_id}/{media_id}.jpg"
        
        # Upload to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=s3_key,
            Body=image_bytes,
            ContentType='image/jpeg'
        )
        
        # Generate presigned URL for response
        image_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=3600
        )
        
        return jsonify({
            'success': True,
            'media': {
                'id': media_id,
                'type': 'image',
                'uri': image_url,
                'thumb': image_url
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/person/<person_id>/media/<media_id>', methods=['DELETE'])
def delete_person_media(person_id, media_id):
    """Delete a specific media item from person's gallery"""
    try:
        s3_key = f"{person_id}/{media_id}.jpg"
        
        # Delete from S3
        s3.delete_object(Bucket=BUCKET_NAME, Key=s3_key)
        
        return jsonify({'success': True, 'message': 'Media deleted successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_person/<person_id>', methods=['DELETE'])
def delete_person(person_id):
    """Delete a person from all AWS services"""
    print(f"[DELETE_PERSON] Request to delete person_id: {person_id}")
    try:
        # Get person info first
        db_response = table.get_item(Key={'person_id': person_id})
        person_info = db_response.get('Item')
        
        if not person_info:
            return jsonify({'error': 'Person not found'}), 404
        
        # Delete from Rekognition (get face_id first)
        face_id = person_info.get('face_id')
        if face_id:
            try:
                rekognition.delete_faces(
                    CollectionId=COLLECTION_ID,
                    FaceIds=[face_id]
                )
            except Exception as e:
                print(f"Error deleting from Rekognition: {e}")
        
        # Delete all media from S3 (entire person folder)
        try:
            response = s3.list_objects_v2(Bucket=BUCKET_NAME, Prefix=f"{person_id}/")
            if 'Contents' in response:
                delete_keys = [{'Key': obj['Key']} for obj in response['Contents']]
                s3.delete_objects(
                    Bucket=BUCKET_NAME,
                    Delete={'Objects': delete_keys}
                )
        except Exception as e:
            print(f"Error deleting media from S3: {e}")
        
        # Delete from DynamoDB
        table.delete_item(Key={'person_id': person_id})
        
        return jsonify({'success': True, 'message': 'Person deleted successfully'})
        
    except Exception as e:
        print(f"Delete person error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    print("[HEALTH] Health check requested")
    return jsonify({'status': 'healthy'})

@app.route('/test-tts', methods=['GET'])
def test_tts():
    """Test TTS audio generation"""
    try:
        test_text = "This is John Smith, your son, age 35."
        audio_base64 = generate_tts_audio(test_text)
        
        if audio_base64:
            return jsonify({
                'success': True,
                'audio': audio_base64,
                'text': test_text,
                'audio_length': len(audio_base64)
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate audio'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/generate-audio', methods=['POST'])
def generate_audio():
    """Generate TTS audio for arbitrary text"""
    try:
        data = request.get_json()
        text = data.get('text')
        
        if not text:
            return jsonify({'error': 'Text is required'}), 400
        
        audio_base64 = generate_tts_audio(text)
        
        if audio_base64:
            return jsonify({
                'success': True,
                'audio': audio_base64,
                'text': text
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to generate audio'
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug-person/<person_id>', methods=['GET'])
def debug_person(person_id):
    """Debug a specific person's data and audio generation"""
    try:
        # Get person info from DynamoDB
        db_response = table.get_item(Key={'person_id': person_id})
        person_info = db_response.get('Item')
        
        if not person_info:
            return jsonify({'error': 'Person not found'}), 404
        
        # Create announcement
        name = person_info.get('name', 'Unknown person')
        relationship = person_info.get('relationship', 'Unknown role')
        age = person_info.get('age', 'Unknown age')
        announcement = f"This is {name}, your {relationship}, age {age}."
        
        # Generate audio
        audio_base64 = generate_tts_audio(announcement)
        
        return jsonify({
            'person_info': {
                'name': name,
                'relationship': relationship,
                'age': age
            },
            'announcement': announcement,
            'audio_generated': bool(audio_base64),
            'audio_length': len(audio_base64) if audio_base64 else 0,
            'audio': audio_base64 if audio_base64 else None
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8000)