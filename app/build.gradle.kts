plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.angel.championshud"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.angel.championshud"
        minSdk = 29
        targetSdk = 35
        versionCode = 3
        versionName = "0.3"
    }

    // Firma propia para poder pasarle el APK a otra persona e instalarlo.
    // Un APK "debug" tambien se instala, pero Android lo trata peor y hay
    // lanzadores que lo rechazan; este queda como una app normal.
    signingConfigs {
        create("share") {
            storeFile = file("championshud.jks")
            storePassword = "champions"
            keyAlias = "champions"
            keyPassword = "champions"
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            // Si el archivo de firma no existe todavia, compila igual sin firmar.
            if (file("championshud.jks").exists()) {
                signingConfig = signingConfigs.getByName("share")
            }
        }
    }

    // Un solo APK universal: mas pesado pero se lo pasas a cualquiera.
    splits { abi { isEnable = false } }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
    // Variante "bundled": el modelo va empaquetado en el APK (~20MB más),
    // no se descarga la primera vez por Play Services — offline-first real
    // (decisions.md #6), no la variante liviana que depende de red al inicio.
    implementation("com.google.mlkit:text-recognition:16.0.0")
}
