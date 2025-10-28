// ✅ Crypto-JS 사용 (CDN으로 로드됨)
function encryptAES(plainText, password) {
    const salt = CryptoJS.lib.WordArray.random(16); // 16바이트 Salt 생성

    // ✅ PBKDF2를 사용하여 키 & IV 생성 (C#과 동일한 10000회 반복, SHA-256)
    const keyAndIV = CryptoJS.PBKDF2(password, salt, {
        keySize: (32 + 16) / 4, // 256-bit Key + 128-bit IV
        iterations: 10000,
        hasher: CryptoJS.algo.SHA256
    });

    // ✅ 키 & IV 분리
    const key = CryptoJS.lib.WordArray.create(keyAndIV.words.slice(0, 8)); // 32바이트 키
    const iv = CryptoJS.lib.WordArray.create(keyAndIV.words.slice(8, 12)); // 16바이트 IV

    // ✅ AES-CBC 암호화
    const encrypted = CryptoJS.AES.encrypt(plainText, key, {
        iv: iv,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    });

    // ✅ Salt + 암호화된 데이터 합쳐서 Base64 변환 (C#과 동일한 방식)
    const encryptedBytes = salt.concat(encrypted.ciphertext);
    return CryptoJS.enc.Base64.stringify(encryptedBytes);
}

function decryptAES(cipherText, password) {
    const encryptedBytes = CryptoJS.enc.Base64.parse(cipherText); // Base64 디코딩

    // ✅ Salt (16바이트) 및 암호화된 데이터 분리
    const salt = CryptoJS.lib.WordArray.create(encryptedBytes.words.slice(0, 4)); // 첫 16바이트는 Salt
    const encryptedData = CryptoJS.lib.WordArray.create(encryptedBytes.words.slice(4)); // 나머지는 암호화된 데이터

    // ✅ PBKDF2로 키 & IV 복원 (C#과 동일한 방식)
    const keyAndIV = CryptoJS.PBKDF2(password, salt, {
        keySize: (32 + 16) / 4,
        iterations: 10000,
        hasher: CryptoJS.algo.SHA256
    });

    const key = CryptoJS.lib.WordArray.create(keyAndIV.words.slice(0, 8)); // 32바이트 키
    const iv = CryptoJS.lib.WordArray.create(keyAndIV.words.slice(8, 12)); // 16바이트 IV

    // ✅ AES-CBC 복호화
    const decrypted = CryptoJS.AES.decrypt({ ciphertext: encryptedData }, key, {
        iv: iv,
        mode: CryptoJS.mode.CBC,
        padding: CryptoJS.pad.Pkcs7
    });

    return CryptoJS.enc.Utf8.stringify(decrypted);
}

// ✅ `window` 객체에 등록 (HTML에서 `cryptoUtils.js` 로드 후 전역 접근 가능)
window.encryptAES = encryptAES;
window.decryptAES = decryptAES;
