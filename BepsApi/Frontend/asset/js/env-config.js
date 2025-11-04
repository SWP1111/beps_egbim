/**
 * Environment Configuration
 * 
 * ⚠️ IMPORTANT: When changing IP addresses, only modify the values below:
 * - API_HOST: The IP address or hostname of your backend server
 * - API_PORT: The port number your backend server is running on
 * 
 * All other files will automatically use these values.
 */

const ENV_CONFIG = {
    API_HOST: '172.16.40.192',
    API_PORT: '20000'
};

// Build the complete URLs
const API_BASE_URL = `http://${ENV_CONFIG.API_HOST}:${ENV_CONFIG.API_PORT}/`;
const WEBSOCKET_URL = `ws://${ENV_CONFIG.API_HOST}:${ENV_CONFIG.API_PORT}/websocket/`;

// Make these available globally for backward compatibility
window.ENV_CONFIG = ENV_CONFIG;
window.API_BASE_URL = API_BASE_URL;
window.WEBSOCKET_URL = WEBSOCKET_URL;

// Also set baseUrl for backward compatibility with existing code
window.baseUrl = API_BASE_URL;
window.websocketUrl = WEBSOCKET_URL;

console.log('✅ Environment configuration loaded:');
console.log('   API Base URL:', API_BASE_URL);
console.log('   WebSocket URL:', WEBSOCKET_URL);
