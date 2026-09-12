# Keep OpenCV JNI and utility classes
-keep class org.opencv.** { *; }
-keepclassmembers class org.opencv.** { *; }

# Keep native methods and classes containing them
-keepclasseswithmembernames class * {
    native <methods>;
}

# Keep our domain data models for safe serialization/deserialization if needed
-keep class com.example.facecount.domain.model.** { *; }
