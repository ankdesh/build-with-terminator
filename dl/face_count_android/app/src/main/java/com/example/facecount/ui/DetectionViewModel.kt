package com.example.facecount.ui

import android.graphics.Bitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.facecount.domain.detector.FaceDetector
import com.example.facecount.domain.model.DetectionResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * ViewModel managing face detection UI state and coordinating vision engine inference.
 */
class DetectionViewModel(
    private val faceDetector: FaceDetector
) : ViewModel() {

    private val _uiState = MutableStateFlow(DetectionUiState())
    val uiState: StateFlow<DetectionUiState> = _uiState.asStateFlow()

    // Cache the raw detections performed at a low base threshold (0.1f)
    // allowing instantaneous, smooth slider filtering without repeated native inference.
    private var cachedRawResult: DetectionResult? = null

    /**
     * Ingests a new bitmap, performs face detection via YuNet, and updates state.
     */
    fun processBitmap(bitmap: Bitmap) {
        _uiState.update {
            it.copy(
                selectedBitmap = bitmap,
                isLoading = true,
                errorMessage = null
            )
        }

        viewModelScope.launch {
            try {
                val currentThreshold = _uiState.value.scoreThreshold
                val result = withContext(Dispatchers.Default) {
                    // Detect with base threshold 0.1f to capture partial/low-confidence faces
                    faceDetector.detect(bitmap, scoreThreshold = 0.1f)
                }

                cachedRawResult = result
                val filtered = result.faces.filter { it.score >= currentThreshold }

                _uiState.update {
                    it.copy(
                        detectionResult = result,
                        filteredFaces = filtered,
                        isLoading = false
                    )
                }
            } catch (e: Exception) {
                _uiState.update {
                    it.copy(
                        isLoading = false,
                        errorMessage = "Detection failed: ${e.localizedMessage ?: "Unknown error"}"
                    )
                }
            }
        }
    }

    /**
     * Reacts to user adjusting the confidence threshold slider.
     */
    fun onThresholdChanged(newThreshold: Float) {
        val clamped = newThreshold.coerceIn(0.1f, 0.95f)
        val raw = cachedRawResult
        val filtered = raw?.faces?.filter { it.score >= clamped } ?: emptyList()

        _uiState.update {
            it.copy(
                scoreThreshold = clamped,
                filteredFaces = filtered
            )
        }
    }

    /**
     * Clears the current image and detection results.
     */
    fun clearImage() {
        cachedRawResult = null
        _uiState.update {
            DetectionUiState(scoreThreshold = it.scoreThreshold)
        }
    }

    /**
     * Dismisses the error message banner.
     */
    fun dismissError() {
        _uiState.update { it.copy(errorMessage = null) }
    }
}
