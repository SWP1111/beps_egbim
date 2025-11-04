/**
 * ⚠️ DEPRECATED: This file is kept for backward compatibility only.
 * Configuration is now loaded from env-config.js
 * 
 * To change IP addresses, edit: asset/js/env-config.js
 */

// These values are set by env-config.js (loaded before this file)
// If env-config.js hasn't loaded for some reason, use fallback values
const baseUrl = window.baseUrl || "http://172.16.40.192:20000/";
window.baseUrl = baseUrl;

const websocketUrl = window.websocketUrl || "ws://172.16.40.192:20000/websocket/";
window.websocketUrl = websocketUrl;

console.log("✅ config.js loaded. baseUrl =", window.baseUrl);

