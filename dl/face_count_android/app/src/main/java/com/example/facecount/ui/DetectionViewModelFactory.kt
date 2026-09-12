package com.example.facecount.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.example.facecount.domain.detector.FaceDetector

/**
 * Factory for creating [DetectionViewModel] instances with injected [FaceDetector].
 */
class DetectionViewModelFactory(
    private val faceDetector: FaceDetector
) : ViewModelProvider.Factory {

    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T {
        if (modelClass.isAssignableFrom(DetectionViewModel::class.java)) {
            return DetectionViewModel(faceDetector) as T
        }
        throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
    }
}
