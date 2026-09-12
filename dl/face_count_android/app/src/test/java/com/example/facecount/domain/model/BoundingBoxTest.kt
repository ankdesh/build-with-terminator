package com.example.facecount.domain.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit test verifying BoundingBox normalization and boundary validation.
 */
class BoundingBoxTest {

    @Test
    fun testValidBoundingBoxProperties() {
        val box = BoundingBox(
            left = 0.1f,
            top = 0.2f,
            right = 0.5f,
            bottom = 0.7f
        )

        assertEquals(0.4f, box.width, 0.001f)
        assertEquals(0.5f, box.height, 0.001f)
    }

    @Test(expected = IllegalArgumentException::class)
    fun testInvalidLeftRightBoundingBoxThrows() {
        BoundingBox(
            left = 0.8f,
            top = 0.2f,
            right = 0.3f,
            bottom = 0.7f
        )
    }

    @Test(expected = IllegalArgumentException::class)
    fun testInvalidTopBottomBoundingBoxThrows() {
        BoundingBox(
            left = 0.1f,
            top = 0.9f,
            right = 0.5f,
            bottom = 0.2f
        )
    }
}
