package com.example.facecount.data.util

import android.content.Context
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

/**
 * Manages extraction and location of bundled ONNX model assets.
 */
class ModelAssetManager(private val context: Context) {

    companion object {
        const val YUNET_MODEL_NAME = "face_detection_yunet_2023mar.onnx"
        private const val ASSET_MODEL_PATH = "models/$YUNET_MODEL_NAME"
    }

    /**
     * Ensures the YuNet ONNX model is extracted from assets to internal storage
     * and returns its absolute filesystem path.
     */
    @Throws(IOException::class)
    fun getYuNetModelPath(): String {
        val modelsDir = File(context.filesDir, "models")
        if (!modelsDir.exists()) {
            modelsDir.mkdirs()
        }

        val targetFile = File(modelsDir, YUNET_MODEL_NAME)

        // Read asset file descriptor or check if already copied
        val assetManager = context.assets
        val shouldCopy = !targetFile.exists() || targetFile.length() == 0L

        if (shouldCopy) {
            assetManager.open(ASSET_MODEL_PATH).use { input ->
                FileOutputStream(targetFile).use { output ->
                    input.copyTo(output)
                }
            }
        }

        if (!targetFile.exists() || targetFile.length() == 0L) {
            throw IOException("Failed to extract model file from assets: $ASSET_MODEL_PATH")
        }

        return targetFile.absolutePath
    }
}
