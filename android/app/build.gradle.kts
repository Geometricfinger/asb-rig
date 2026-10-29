plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

val commit: String = System.getenv("ASB_COMMIT") ?: "dev"

android {
    namespace = "org.asbrig.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "org.asbrig.app"
        minSdk = 29
        targetSdk = 34
        versionCode = 1
        versionName = "0.1.0"
        buildConfigField("String", "COMMIT", "\"$commit\"")
    }
    buildFeatures { buildConfig = true }
    buildTypes {
        release { isMinifyEnabled = false }   // unsigned; signing is the user's own step
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    sourceSets["main"].assets.srcDirs("src/main/assets", "../../schema")
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.fragment:fragment-ktx:1.8.2")
    implementation("androidx.biometric:biometric:1.1.0")
    implementation("androidx.camera:camera-core:1.3.4")
    implementation("androidx.camera:camera-camera2:1.3.4")
    implementation("androidx.camera:camera-lifecycle:1.3.4")
    implementation("net.zetetic:sqlcipher-android:4.6.1")
    implementation("androidx.sqlite:sqlite:2.4.0")
    implementation("org.mapsforge:mapsforge-map-android:0.21.0")
    implementation("org.mapsforge:mapsforge-themes:0.21.0")
}
