package com.example.facecount.data.detector

import android.graphics.Bitmap
import android.os.SystemClock
import com.example.facecount.data.util.BitmapUtils
import com.example.facecount.domain.detector.FaceDetector
import com.example.facecount.domain.model.BoundingBox
import com.example.facecount.domain.model.DetectionResult
import com.example.facecount.domain.model.FaceDetection
import com.example.facecount.domain.model.Landmark
import org.opencv.core.Mat
import org.opencv.core.Size
import org.opencv.objdetect.FaceDetectorYN

/**
 * High-performance FaceDetector implementation utilizing OpenCV YuNet (FaceDetectorYN).
 *
 * YuNet is a lightweight ONNX model (~232 KB) designed for robust face detection
 * under challenging conditions including profile views, tilted angles, and partial occlusions.
 */
class OpenCVYuNetDetector(
    private val modelPath: String
) : FaceDetector {

    private val detector: FaceDetectorYN by lazy {
        FaceDetectorYN.create(
            modelPath,
            "",
            Size(320.0, 320.0),
            0.6f,
            0.3f,
            5000
        ) ?: throw IllegalStateException("Failed to initialize FaceDetectorYN with model: $modelPath")
    }

    override fun detect(
        bitmap: Bitmap,
        scoreThreshold: Float,
        nmsThreshold: Float
    ): DetectionResult {
        val startTime = SystemClock.elapsedRealtime()

        val imageWidth = bitmap.width
        val imageHeight = bitmap.height
        val bgrMat = BitmapUtils.bitmapToBgrMat(bitmap)
        val facesMat = Mat()

        return try {
            // Update input dimensions and thresholds for the current image
            detector.setInputSize(Size(bgrMat.width().toDouble(), bgrMat.height().toDouble()))
            detector.setScoreThreshold(scoreThreshold)
            detector.setNMSThreshold(nmsThreshold)

            // Run YuNet inference
            detector.detect(bgrMat, facesMat)

            val detectedFaces = mutableListOf<FaceDetection>()
            val numFaces = facesMat.rows()

            for (i in 0 until numFaces) {
                // YuNet output row structure:
                // [0..3]: x, y, width, height
                // [4..13]: 5 facial landmarks (x, y)
                // [14]: confidence score
                val x = facesMat.get(i, 0)[0].toFloat()
                val y = facesMat.get(i, 1)[0].toFloat()
                val w = facesMat.get(i, 2)[0].toFloat()
                val h = facesMat.get(i, 3)[0].toFloat()
                val score = facesMat.get(i, 14)[0].toFloat()

                // Normalize coordinates to [0.0, 1.0]
                val left = (x / imageWidth).coerceIn(0f, 1f)
                val top = (y / imageHeight).coerceIn(0f, 1f)
                val right = ((x + w) / imageWidth).coerceIn(left, 1f)
                val bottom = ((y + h) / imageHeight).coerceIn(top, 1f)

                val landmarks = mutableListOf<Landmark>()
                for (lmIdx in 0 until 5) {
                    val lmX = facesMat.get(i, 4 + lmIdx * 2)[0].toFloat() / imageWidth
                    val lmY = facesMat.get(i, 5 + lmIdx * 2)[0].toFloat() / imageHeight
                    landmarks.add(Landmark(lmX.coerceIn(0f, 1f), lmY.coerceIn(0f, 1f)))
                }

                detectedFaces.add(
                    FaceDetection(
                        id = i + 1,
                        boundingBox = BoundingBox(left, top, right, bottom),
                        score = score,
                        landmarks = landmarks
                    )
                )
            }

            val inferenceTime = SystemClock.elapsedRealtime() - startTime
            DetectionResult(
                faces = detectedFaces,
                inferenceTimeMs = inferenceTime,
                imageWidth = imageWidth,
                imageHeight = imageHeight
            )
        } finally {
            bgrMat.release()
            facesMat.release()
        }
    }
}
