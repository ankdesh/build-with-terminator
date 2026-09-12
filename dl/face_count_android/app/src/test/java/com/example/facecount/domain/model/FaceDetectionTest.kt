package com.example.facecount.domain.model

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * Unit test verifying FaceDetection data integrity and landmark associations.
 */
class FaceDetectionTest {

    @Test
    fun testFaceDetectionWithLandmarks() {
        val landmarks = listOf(
            Landmark(0.3f, 0.4f),
            Landmark(0.5f, 0.4f),
            Landmark(0.4f, 0.5f),
            Landmark(0.35f, 0.6f),
            Landmark(0.45f, 0.6f)
        )

        val detection = FaceDetection(
            id = 1,
            boundingBox = BoundingBox(0.2f, 0.2f, 0.6f, 0.7f),
            score = 0.91f,
            landmarks = landmarks
        )

        assertEquals(1, detection.id)
        assertEquals(0.91f, detection.score, 0.001f)
        assertEquals(5, detection.landmarks.size)
        assertEquals(0.3f, detection.landmarks[0].x, 0.001f)
    }
}
