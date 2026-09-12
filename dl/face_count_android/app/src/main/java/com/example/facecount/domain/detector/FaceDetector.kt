package com.example.facecount.domain.detector

import android.graphics.Bitmap
import com.example.facecount.domain.model.DetectionResult

/**
 * Interface contract for face detection engines.
 */
interface FaceDetector {
    /**
     * Analyzes the provided bitmap and detects faces.
     *
     * @param bitmap The image bitmap to analyze.
     * @param scoreThreshold Minimum confidence score required to retain a face [0.0, 1.0].
     * @param nmsThreshold Non-maximum suppression threshold to remove overlapping duplicates.
     * @return [DetectionResult] containing detected faces, bounding boxes, and performance metrics.
     */
    fun detect(
        bitmap: Bitmap,
        scoreThreshold: Float = 0.6f,
        nmsThreshold: Float = 0.3f
    ): DetectionResult
}
