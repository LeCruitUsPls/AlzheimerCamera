// Use your computer's IP address for mobile testing
const API_BASE_URL = __DEV__ ? 'http://localhost:8000' : 'http://localhost:8000';

export const api = {
  // Recognize a person from image
  async recognizePerson(imageBase64) {
    const response = await fetch(`${API_BASE_URL}/recognize`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageBase64
      })
    });
    return response.json();
  },

  // Add a new person
  async addPerson(imageBase64, name, relationship, age, notes) {
    const response = await fetch(`${API_BASE_URL}/add_person`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageBase64,
        name,
        relationship,
        age: parseInt(age) || null,
        notes
      })
    });
    return response.json();
  },

  // Get all people (reminders)
  async getReminders() {
    const response = await fetch(`${API_BASE_URL}/reminders`);
    return response.json();
  },

  // Edit a person
  async editPerson(personId, name, relationship, age, notes, images = []) {
    const response = await fetch(`${API_BASE_URL}/edit_person/${personId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name,
        relationship,
        age: parseInt(age) || null,
        notes,
        images
      })
    });
    return response.json();
  },

  // Delete a person
  async deletePerson(personId) {
    const response = await fetch(`${API_BASE_URL}/delete_person/${personId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    return response.json();
  },

  // Get person details
  async getPersonDetails(personId) {
    const response = await fetch(`${API_BASE_URL}/person/${personId}`);
    return response.json();
  },

  // Get person's media gallery
  async getPersonMedia(personId) {
    const response = await fetch(`${API_BASE_URL}/person/${personId}/media`);
    return response.json();
  },

  // Add image to person's gallery
  async addPersonMedia(personId, imageBase64) {
    const response = await fetch(`${API_BASE_URL}/person/${personId}/media`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: imageBase64
      })
    });
    return response.json();
  },

  // Delete specific media from person's gallery
  async deletePersonMedia(personId, mediaId) {
    const response = await fetch(`${API_BASE_URL}/person/${personId}/media/${mediaId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    return response.json();
  },

  // Health check
  async healthCheck() {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.json();
  }
};

// Helper function to convert image URI to base64 (React Native compatible)
export const imageToBase64 = async (imageUri) => {
  try {
    const response = await fetch(imageUri);
    const blob = await response.blob();
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64 = reader.result.split(',')[1];
        resolve(base64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
  } catch (error) {
    console.error('Error converting image to base64:', error);
    throw error;
  }
};

// Helper function to convert multiple image URIs to base64
export const imagesToBase64 = async (imageUris) => {
  try {
    const promises = imageUris.map(uri => imageToBase64(uri));
    return await Promise.all(promises);
  } catch (error) {
    console.error('Error converting images to base64:', error);
    throw error;
  }
};

// Update person with gallery images
export const updatePersonWithImages = async (personId, personData, imageUris = []) => {
  try {
    let images = [];
    if (imageUris.length > 0) {
      images = await imagesToBase64(imageUris);
    }
    
    return await api.editPerson(
      personId,
      personData.name,
      personData.relationship,
      personData.age,
      personData.notes,
      images
    );
  } catch (error) {
    console.error('Error updating person with images:', error);
    throw error;
  }
};

// Test connection
export const testConnection = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    const result = await response.json();
    console.log('Backend connection:', result);
    return result;
  } catch (error) {
    console.error('Backend connection failed:', error);
    throw error;
  }
};