package com.example.facecount.domain.model

/**
 * Represents a normalized bounding box in relative coordinates [0.0, 1.0].
 */
data class BoundingBox(
    val left: Float,
    val top: Float,
    val right: Float,
    val bottom: Float
) {
    val width: Float
        get() = (right - left).coerceAtLeast(0f)

    val height: Float
        get() = (bottom - top).coerceAtLeast(0f)

    init {
        require(left <= right) { "BoundingBox left ($left) cannot be greater than right ($right)" }
        require(top <= bottom) { "BoundingBox top ($top) cannot be greater than bottom ($bottom)" }
    }
}
