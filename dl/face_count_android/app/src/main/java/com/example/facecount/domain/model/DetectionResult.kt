package com.example.facecount.domain.model

/**
 * Encapsulates the complete result of face detection over an image.
 */
data class DetectionResult(
    val faces: List<FaceDetection>,
    val inferenceTimeMs: Long,
    val imageWidth: Int,
    val imageHeight: Int
) {
    val faceCount: Int
        get() = faces.size
}
