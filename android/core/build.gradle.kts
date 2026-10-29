plugins {
    id("org.jetbrains.kotlin.jvm")
}

// Pure-Kotlin core shared with the app: Noise_XX link (byte-compatible with the Python pod),
// enrollment protocol + flow, alert visuals. Checked on the JVM without a test framework
// dependency (`jvmChecks`, part of `check`), against vectors in ../../tests/vectors.
java {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
}
tasks.withType<org.jetbrains.kotlin.gradle.tasks.KotlinCompile>().configureEach { kotlinOptions.jvmTarget = "17" }

dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.78.1")
}

val jvmCheck by sourceSets.creating {
    compileClasspath += sourceSets["main"].output + configurations["runtimeClasspath"]
    runtimeClasspath += output + compileClasspath
}

val jvmChecks by tasks.registering(JavaExec::class) {
    description = "Runs the core JVM checks (Noise vectors, protocol, enrollment flow, alert visuals)."
    group = "verification"
    classpath = jvmCheck.runtimeClasspath
    mainClass.set("org.oiris.core.ChecksKt")
    args(rootDir.parentFile.absolutePath)
}
tasks.named("check") { dependsOn(jvmChecks) }
