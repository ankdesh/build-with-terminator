package com.example.facecount.domain.model

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Unit test verifying DetectionResult metrics and face count calculation.
 */
class DetectionResultTest {

    @Test
    fun testFaceCountAggregation() {
        val faces = listOf(
            FaceDetection(
                id = 1,
                boundingBox = BoundingBox(0.1f, 0.1f, 0.3f, 0.3f),
                score = 0.95f
            ),
            FaceDetection(
                id = 2,
                boundingBox = BoundingBox(0.5f, 0.4f, 0.8f, 0.7f),
                score = 0.82f
            )
        )

        val result = DetectionResult(
            faces = faces,
            inferenceTimeMs = 45L,
            imageWidth = 1280,
            imageHeight = 720
        )

        assertEquals(2, result.faceCount)
        assertEquals(45L, result.inferenceTimeMs)
        assertEquals(1280, result.imageWidth)
        assertEquals(720, result.imageHeight)
    }

    @Test
    fun testEmptyDetectionResult() {
        val result = DetectionResult(
            faces = emptyList(),
            inferenceTimeMs = 30L,
            imageWidth = 640,
            imageHeight = 480
        )

        assertEquals(0, result.faceCount)
    }
}
