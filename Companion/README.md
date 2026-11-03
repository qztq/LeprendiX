npm ci
npm run android:stage
npx cap add android   # nur beim ersten Mal
npx cap sync android
npm run android:prepare -- --version-code 1 --version-name 1.0.0
cd android
.\gradlew.bat assembleDebug

android\app\build\outputs\apk\debug\app-debug.apk