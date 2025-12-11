/**
 * Environment Variable Build Script
 * .envファイルを読み込み、TypeScript設定ファイルを生成
 */

const fs = require('fs');
const path = require('path');

const ENV_FILE = path.join(__dirname, '.env');
const OUTPUT_FILE = path.join(__dirname, 'src', 'env-config.ts');

function parseEnvFile(filePath) {
  if (!fs.existsSync(filePath)) {
    console.error('❌ .envファイルが見つかりません。.env.exampleを参考に作成してください。');
    process.exit(1);
  }

  const content = fs.readFileSync(filePath, 'utf-8');
  const env = {};

  content.split('\n').forEach(line => {
    line = line.trim();
    if (line && !line.startsWith('#')) {
      const [key, ...valueParts] = line.split('=');
      if (key && valueParts.length > 0) {
        env[key.trim()] = valueParts.join('=').trim();
      }
    }
  });

  return env;
}

function generateConfigFile(env) {
  const config = {
    apiKey: env.FIREBASE_API_KEY || '',
    authDomain: env.FIREBASE_AUTH_DOMAIN || '',
    projectId: env.FIREBASE_PROJECT_ID || '',
    storageBucket: env.FIREBASE_STORAGE_BUCKET || '',
    messagingSenderId: env.FIREBASE_MESSAGING_SENDER_ID || '',
    appId: env.FIREBASE_APP_ID || ''
  };

  const tsContent = `/**
 * Firebase Configuration (Auto-generated from .env)
 * このファイルは自動生成されます。直接編集しないでください。
 * 変更する場合は .env ファイルを編集してください。
 */

export const DEFAULT_FIREBASE_CONFIG = {
  apiKey: "${config.apiKey}",
  authDomain: "${config.authDomain}",
  projectId: "${config.projectId}",
  storageBucket: "${config.storageBucket}",
  messagingSenderId: "${config.messagingSenderId}",
  appId: "${config.appId}"
};
`;

  fs.writeFileSync(OUTPUT_FILE, tsContent, 'utf-8');
  console.log('✅ env-config.ts を生成しました');
}

try {
  const env = parseEnvFile(ENV_FILE);
  generateConfigFile(env);
} catch (error) {
  console.error('❌ ビルドエラー:', error.message);
  process.exit(1);
}
