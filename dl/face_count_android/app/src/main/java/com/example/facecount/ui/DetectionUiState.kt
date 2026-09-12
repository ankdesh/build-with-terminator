package com.example.facecount.ui

import android.graphics.Bitmap
import com.example.facecount.domain.model.DetectionResult
import com.example.facecount.domain.model.FaceDetection

/**
 * Immutable UI state for the face detection screen.
 */
data class DetectionUiState(
    val selectedBitmap: Bitmap? = null,
    val detectionResult: DetectionResult? = null,
    val filteredFaces: List<FaceDetection> = emptyList(),
    val scoreThreshold: Float = 0.6f,
    val isLoading: Boolean = false,
    val errorMessage: String? = null
) {
    val faceCount: Int
        get() = filteredFaces.size

    val hasImage: Boolean
        get() = selectedBitmap != null
}
