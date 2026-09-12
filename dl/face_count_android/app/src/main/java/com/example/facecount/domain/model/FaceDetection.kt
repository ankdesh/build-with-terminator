package com.example.facecount.domain.model

/**
 * Represents a single detected face entity.
 */
data class FaceDetection(
    val id: Int,
    val boundingBox: BoundingBox,
    val score: Float,
    val landmarks: List<Landmark> = emptyList()
)
