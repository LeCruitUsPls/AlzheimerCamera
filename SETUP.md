# AlzheimerCamera Setup Guide

## Prerequisites
- Python 3.8+
- Node.js 18+
- AWS Account with credentials configured
- ElevenLabs API key (optional, for TTS)

## Quick Start Commands

### 1. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install flask flask-cors boto3 python-dotenv pillow requests pillow-heif
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your AWS credentials and settings
```

### 3. Setup AWS Resources
```bash
python3 setup_aws.py
```

### 4. Start Backend
```bash
python3 app.py
```

### 5. Frontend Setup
```bash
cd ../frontend
npm install
```

### 6. Update API URL
Edit `frontend/services/api.js` and update the IP address:
```javascript
const API_BASE_URL = __DEV__ ? 'http://YOUR_IP:8000' : 'http://localhost:8000';
```

### 7. Start Frontend
```bash
npm start
```

## Environment Variables (.env)

Required:
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET_NAME=alzheimer-camera-faces
REKOGNITION_COLLECTION_ID=alzheimer-faces
DYNAMODB_TABLE_NAME=alzheimer-persons
```

Optional (for TTS):
```
ELEVEN_LAB_API_KEY=your_elevenlabs_key
VOICE_ID=your_voice_id
```

## Testing
```bash
# Test backend
cd backend
python3 test_simple.py

# Test frontend connection
# Open app and check console for "Backend connection" logs
```

## Troubleshooting

### Backend Issues
- Ensure AWS credentials are valid
- Check if port 8000 is available: `lsof -ti:8000`
- Verify all Python dependencies are installed

### Frontend Issues
- Update IP address in api.js for mobile testing
- Ensure backend is running before starting frontend
- Check Expo CLI is installed: `npm install -g @expo/cli`

### AWS Issues
- Verify AWS credentials have proper permissions
- Check if resources already exist before running setup
- Ensure region is consistent across all services