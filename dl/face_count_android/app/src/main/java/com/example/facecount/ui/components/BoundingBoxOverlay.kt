package com.example.facecount.ui.components

import android.graphics.Paint
import android.graphics.Rect
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.unit.dp
import com.example.facecount.domain.model.FaceDetection
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Canvas overlay that draws accurate bounding boxes, confidence tags, and facial landmarks
 * over the rendered bitmap adhering to aspect-fit scaling.
 */
@Composable
fun BoundingBoxOverlay(
    faces: List<FaceDetection>,
    imageWidth: Int,
    imageHeight: Int,
    modifier: Modifier = Modifier,
    boxColor: Color = Color(0xFF00E676),
    landmarkColor: Color = Color(0xFF00E5FF)
) {
    if (faces.isEmpty() || imageWidth <= 0 || imageHeight <= 0) {
        return
    }

    Canvas(modifier = modifier.fillMaxSize()) {
        val viewportW = size.width
        val viewportH = size.height

        // Calculate aspect-fit geometry
        val scale = min(viewportW / imageWidth.toFloat(), viewportH / imageHeight.toFloat())
        val displayedW = imageWidth * scale
        val displayedH = imageHeight * scale
        val offsetX = (viewportW - displayedW) / 2f
        val offsetY = (viewportH - displayedH) / 2f

        val strokeWidthPx = 3.dp.toPx()
        val cornerRadius = CornerRadius(8.dp.toPx(), 8.dp.toPx())

        for (face in faces) {
            val box = face.boundingBox
            val left = offsetX + box.left * displayedW
            val top = offsetY + box.top * displayedH
            val right = offsetX + box.right * displayedW
            val bottom = offsetY + box.bottom * displayedH
            val boxW = (right - left).coerceAtLeast(1f)
            val boxH = (bottom - top).coerceAtLeast(1f)

            // 1. Draw Bounding Box Rectangle
            drawRoundRect(
                color = boxColor,
                topLeft = Offset(left, top),
                size = Size(boxW, boxH),
                cornerRadius = cornerRadius,
                style = Stroke(width = strokeWidthPx)
            )

            // 2. Draw Confidence & Index Label Badge
            val labelText = "#${face.id} (${(face.score * 100).roundToInt()}%)"
            drawLabel(
                text = labelText,
                x = left,
                y = top,
                backgroundColor = boxColor
            )

            // 3. Draw 5 Facial Landmarks (eyes, nose, mouth corners)
            for (landmark in face.landmarks) {
                val lmX = offsetX + landmark.x * displayedW
                val lmY = offsetY + landmark.y * displayedH
                drawCircle(
                    color = landmarkColor,
                    radius = 3.5.dp.toPx(),
                    center = Offset(lmX, lmY)
                )
            }
        }
    }
}

private fun DrawScope.drawLabel(
    text: String,
    x: Float,
    y: Float,
    backgroundColor: Color
) {
    val textPaint = Paint().apply {
        color = android.graphics.Color.BLACK
        textSize = 12.dp.toPx()
        isFakeBoldText = true
        isAntiAlias = true
    }

    val textBounds = Rect()
    textPaint.getTextBounds(text, 0, text.length, textBounds)
    val padding = 6.dp.toPx()
    val badgeW = textBounds.width() + padding * 2
    val badgeH = textBounds.height() + padding * 1.5f

    // Draw above the box, or inside if too close to top
    val badgeTop = if (y - badgeH >= 0) y - badgeH else y
    val badgeLeft = x.coerceAtLeast(0f)

    drawRoundRect(
        color = backgroundColor,
        topLeft = Offset(badgeLeft, badgeTop),
        size = Size(badgeW, badgeH),
        cornerRadius = CornerRadius(4.dp.toPx(), 4.dp.toPx())
    )

    drawContext.canvas.nativeCanvas.drawText(
        text,
        badgeLeft + padding,
        badgeTop + badgeH - padding * 0.6f,
        textPaint
    )
}
