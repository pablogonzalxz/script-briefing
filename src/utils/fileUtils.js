const path = require('path');
const fs = require('fs').promises;

const MIME_TO_EXT = {
  'application/pdf': '.pdf',
  'image/jpeg': '.jpg',
  'image/png': '.png',
  'text/plain': '.txt',
};

function getExtensionFromMimeType(mimeType) {
  return MIME_TO_EXT[mimeType] || '.bin';
}

function sanitizeFilename(filename) {
  return filename.replace(/[^a-zA-Z0-9._-]/g, '_');
}

async function ensureDirectoryExists(dirPath) {
  try {
    await fs.access(dirPath);
  } catch {
    await fs.mkdir(dirPath, { recursive: true });
  }
}

module.exports = {
  getExtensionFromMimeType,
  sanitizeFilename,
  ensureDirectoryExists
};
