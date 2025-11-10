// Test frontend-backend connection
const API_BASE_URL = 'http://localhost:8000';

async function testConnection() {
    console.log('Testing backend connection...');
    
    try {
        // Test health endpoint
        const healthResponse = await fetch(`${API_BASE_URL}/health`);
        const healthData = await healthResponse.json();
        console.log('✅ Health check:', healthData);
        
        // Test add_person endpoint with minimal data
        const testData = {
            image: "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChAI9jU77yQAAAABJRU5ErkJggg==",
            name: "Test Person",
            relationship: "friend",
            age: 30,
            notes: "Test"
        };
        
        console.log('Testing add_person endpoint...');
        const addResponse = await fetch(`${API_BASE_URL}/add_person`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(testData)
        });
        
        const addData = await addResponse.json();
        console.log('Add person response:', addData);
        
    } catch (error) {
        console.error('❌ Connection failed:', error);
    }
}

// Run in Node.js environment
if (typeof require !== 'undefined') {
    const fetch = require('node-fetch');
    testConnection();
} else {
    // Run in browser
    testConnection();
}