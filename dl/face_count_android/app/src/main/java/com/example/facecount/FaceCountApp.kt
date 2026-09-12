package com.example.facecount

import android.app.Application
import android.util.Log
import org.opencv.android.OpenCVLoader

/**
 * Application class initializing OpenCV native runtime.
 */
class FaceCountApp : Application() {

    companion object {
        private const val TAG = "FaceCountApp"
    }

    override fun onCreate() {
        super.onCreate()

        val initialized = OpenCVLoader.initLocal()
        if (initialized) {
            Log.i(TAG, "OpenCV native library initialized successfully.")
        } else {
            Log.e(TAG, "Failed to initialize OpenCV native library.")
        }
    }
}
