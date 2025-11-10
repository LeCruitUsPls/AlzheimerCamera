#!/bin/bash

echo "🚀 Starting AlzheimerCamera"

# Check if we're in the right directory
if [ ! -f "backend/app.py" ]; then
    echo "❌ Please run this script from the AlzheimerCamera root directory"
    exit 1
fi

# Start backend
echo "Starting backend..."
cd backend

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✅ Virtual environment activated"
fi

# Start backend in background
python3 app.py &
BACKEND_PID=$!
echo "✅ Backend started (PID: $BACKEND_PID)"

# Wait a moment for backend to start
sleep 3

# Test backend
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Backend is healthy"
else
    echo "❌ Backend health check failed"
    kill $BACKEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "🎉 Backend is running on http://localhost:8000"
echo ""
echo "To start the frontend:"
echo "  cd frontend"
echo "  npm start"
echo ""
echo "To stop the backend:"
echo "  kill $BACKEND_PID"
echo ""
echo "Press Ctrl+C to stop the backend"

# Keep script running
wait $BACKEND_PID