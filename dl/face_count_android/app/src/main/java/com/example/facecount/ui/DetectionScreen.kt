package com.example.facecount.ui

import android.graphics.Bitmap
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddPhotoAlternate
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.facecount.ui.components.BoundingBoxOverlay
import com.example.facecount.ui.components.ControlPanel
import com.example.facecount.ui.components.FaceCountBadge

/**
 * Top-level screen for face detection and counting.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetectionScreen(
    uiState: DetectionUiState,
    onThresholdChanged: (Float) -> Unit,
    onPickImageClicked: () -> Unit,
    onTakePhotoClicked: () -> Unit,
    onSampleImageClicked: () -> Unit,
    onClearClicked: () -> Unit,
    onDismissError: () -> Unit
) {
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(uiState.errorMessage) {
        uiState.errorMessage?.let { errorMsg ->
            snackbarHostState.showSnackbar(errorMsg)
            onDismissError()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Face Count • YuNet",
                        fontWeight = FontWeight.Bold,
                        fontSize = 20.sp
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background,
                    titleContentColor = MaterialTheme.colorScheme.onBackground
                )
            )
        },
        bottomBar = {
            ControlPanel(
                uiState = uiState,
                onThresholdChanged = onThresholdChanged,
                onPickImageClicked = onPickImageClicked,
                onTakePhotoClicked = onTakePhotoClicked,
                onSampleImageClicked = onSampleImageClicked,
                onClearClicked = onClearClicked
            )
        },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background
    ) { paddingValues ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(paddingValues)
        ) {
            val bitmap = uiState.selectedBitmap
            if (bitmap != null) {
                // Render selected image
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "Analyzed Photo",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier.fillMaxSize()
                )

                // Canvas overlay for bounding boxes and landmarks
                BoundingBoxOverlay(
                    faces = uiState.filteredFaces,
                    imageWidth = bitmap.width,
                    imageHeight = bitmap.height,
                    modifier = Modifier.fillMaxSize()
                )

                // Top Badge with live face count and latency
                FaceCountBadge(
                    uiState = uiState,
                    modifier = Modifier.align(Alignment.TopCenter)
                )
            } else {
                // Empty state placeholder
                EmptyStatePlaceholder(
                    modifier = Modifier.align(Alignment.Center)
                )
            }

            // Loading overlay
            AnimatedVisibility(
                visible = uiState.isLoading,
                enter = fadeIn(),
                exit = fadeOut(),
                modifier = Modifier.align(Alignment.Center)
            ) {
                Box(
                    modifier = Modifier
                        .size(88.dp)
                        .background(
                            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.9f),
                            shape = CircleShape
                        ),
                    contentAlignment = Alignment.Center
                ) {
                    CircularProgressIndicator(
                        color = MaterialTheme.colorScheme.primary,
                        strokeWidth = 4.dp
                    )
                }
            }
        }
    }
}

@Composable
private fun EmptyStatePlaceholder(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier.padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.AddPhotoAlternate,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary.copy(alpha = 0.6f),
            modifier = Modifier.size(72.dp)
        )
        Spacer(modifier = Modifier.height(16.dp))
        Text(
            text = "No Photo Loaded",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onBackground
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Choose an image from storage or capture a new photo to detect and count human faces",
            style = MaterialTheme.typography.bodyMedium,
            textAlign = TextAlign.Center,
            color = MaterialTheme.colorScheme.onBackground.copy(alpha = 0.6f)
        )
    }
}
