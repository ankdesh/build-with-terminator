package com.example.facecount.data.util

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import androidx.exifinterface.media.ExifInterface
import org.opencv.android.Utils
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.imgproc.Imgproc
import java.io.InputStream
import kotlin.math.max
import kotlin.math.roundToInt

/**
 * Utility functions for image decoding, orientation correction, resizing, and Mat conversion.
 */
object BitmapUtils {

    private const val MAX_DIMENSION_PX = 1280

    /**
     * Decodes a Bitmap from an Android Content Uri with orientation fix and downscaling.
     */
    fun decodeUriWithOrientation(context: Context, uri: Uri): Bitmap? {
        val inputStream: InputStream? = context.contentResolver.openInputStream(uri)
        val bitmap = inputStream?.use { BitmapFactory.decodeStream(it) } ?: return null

        val rotationDegrees = getExifRotationDegrees(context, uri)
        val rotatedBitmap = if (rotationDegrees != 0) {
            rotateBitmap(bitmap, rotationDegrees.toFloat())
        } else {
            bitmap
        }

        return resizeIfNeeded(rotatedBitmap, MAX_DIMENSION_PX)
    }

    /**
     * Resizes the bitmap down if width or height exceeds [maxDimensionPx] while preserving aspect ratio.
     */
    fun resizeIfNeeded(bitmap: Bitmap, maxDimensionPx: Int = MAX_DIMENSION_PX): Bitmap {
        val width = bitmap.width
        val height = bitmap.height
        val maxSide = max(width, height)

        if (maxSide <= maxDimensionPx) {
            return bitmap
        }

        val scale = maxDimensionPx.toFloat() / maxSide
        val targetWidth = (width * scale).roundToInt()
        val targetHeight = (height * scale).roundToInt()

        return Bitmap.createScaledBitmap(bitmap, targetWidth, targetHeight, true)
    }

    /**
     * Rotates a bitmap by [degrees].
     */
    fun rotateBitmap(bitmap: Bitmap, degrees: Float): Bitmap {
        val matrix = Matrix().apply { postRotate(degrees) }
        return Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
    }

    /**
     * Extracts EXIF orientation in degrees from a content Uri.
     */
    private fun getExifRotationDegrees(context: Context, uri: Uri): Int {
        return try {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                val exif = ExifInterface(stream)
                when (exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)) {
                    ExifInterface.ORIENTATION_ROTATE_90 -> 90
                    ExifInterface.ORIENTATION_ROTATE_180 -> 180
                    ExifInterface.ORIENTATION_ROTATE_270 -> 270
                    else -> 0
                }
            } ?: 0
        } catch (_: Exception) {
            0
        }
    }

    /**
     * Converts an Android ARGB_8888 Bitmap to an OpenCV BGR Mat for YuNet processing.
     */
    fun bitmapToBgrMat(bitmap: Bitmap): Mat {
        val safeBitmap = if (bitmap.config != Bitmap.Config.ARGB_8888) {
            bitmap.copy(Bitmap.Config.ARGB_8888, false)
        } else {
            bitmap
        }
        val rgbaMat = Mat(safeBitmap.height, safeBitmap.width, CvType.CV_8UC4)
        Utils.bitmapToMat(safeBitmap, rgbaMat)
        if (safeBitmap != bitmap) {
            safeBitmap.recycle()
        }

        val bgrMat = Mat()
        Imgproc.cvtColor(rgbaMat, bgrMat, Imgproc.COLOR_RGBA2BGR)
        rgbaMat.release()

        return bgrMat
    }
}
