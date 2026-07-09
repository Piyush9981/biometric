package com.outpass.app

import android.Manifest
import android.annotation.SuppressLint
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.webkit.*
import androidx.activity.OnBackPressedCallback
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.NotificationCompat
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var swipeRefresh: SwipeRefreshLayout

    private var pendingPermissionRequest: PermissionRequest? = null
    private var pendingGeolocationCallback: GeolocationPermissions.Callback? = null
    private var pendingGeolocationOrigin: String? = null
    private var filePathCallback: ValueCallback<Array<Uri>>? = null

    private var pendingRequestId: String? = null
    private var pollingThread: Thread? = null
    private var isPolling = false
    private val notifiedRequests = mutableSetOf<String>()

    @Volatile
    private var currentWebViewUrl: String? = TARGET_URL

    companion object {
        private const val TARGET_URL = "https://student-outpass-system-sowi.onrender.com"
        private const val PERMISSION_REQUEST_CODE = 1001
        private const val GEOLOCATION_REQUEST_CODE = 1002
        private const val FILE_CHOOSER_REQUEST_CODE = 2002
        private const val NOTIFICATION_PERMISSION_REQUEST_CODE = 1003
        private const val CHANNEL_ID = "gatekeeper_notifications"
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        webView = findViewById(R.id.webView)
        swipeRefresh = findViewById(R.id.swipeRefresh)

        // Configure SwipeRefreshLayout
        swipeRefresh.setOnRefreshListener {
            webView.reload()
        }

        // Add JavascriptInterface for precise scroll and modal handling
        webView.addJavascriptInterface(WebAppInterface(), "AndroidScroll")

        // Configure Cookie Manager
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)

        // Configure WebView Settings
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            useWideViewPort = true
            loadWithOverviewMode = true
            builtInZoomControls = true
            displayZoomControls = false
            setSupportZoom(true)
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }

        // Configure WebView Clients
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                if (!url.isNullOrEmpty()) {
                    currentWebViewUrl = url
                }
                swipeRefresh.isRefreshing = false
                pendingRequestId?.let { requestId ->
                    webView.evaluateJavascript("javascript:if(typeof window.openRequestDetails !== 'undefined') { window.openRequestDetails('$requestId'); }", null)
                    pendingRequestId = null
                }
                
                val js = """
                    function __checkScroll() {
                        if (!window.AndroidScroll) return;
                        var hasOpenModal = document.querySelector('.modal-overlay:not(.hidden), .modal[style*="block"]') != null;
                        if (hasOpenModal) {
                            window.AndroidScroll.setSwipeRefreshEnabled(false);
                            return;
                        }
                        var container = document.querySelector('.main-content');
                        var y = container ? container.scrollTop : window.scrollY;
                        window.AndroidScroll.setSwipeRefreshEnabled(y === 0);
                    }
                    document.addEventListener('scroll', __checkScroll, true);
                    setInterval(__checkScroll, 300);
                    __checkScroll();
                """.trimIndent()
                webView.evaluateJavascript("javascript:(function(){$js})()", null)
            }

            override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                // Return false to let the WebView load the URL itself
                return false
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            // Support Camera & Microphone Permissions in WebView
            override fun onPermissionRequest(request: PermissionRequest) {
                val resources = request.resources
                val permissionsToRequest = mutableListOf<String>()

                if (resources.contains(PermissionRequest.RESOURCE_VIDEO_CAPTURE)) {
                    permissionsToRequest.add(Manifest.permission.CAMERA)
                }
                if (resources.contains(PermissionRequest.RESOURCE_AUDIO_CAPTURE)) {
                    permissionsToRequest.add(Manifest.permission.RECORD_AUDIO)
                }

                if (permissionsToRequest.isEmpty()) {
                    request.grant(resources)
                    return
                }

                pendingPermissionRequest = request

                val ungranted = permissionsToRequest.filter {
                    checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
                }

                if (ungranted.isEmpty()) {
                    request.grant(resources)
                } else {
                    requestPermissions(ungranted.toTypedArray(), PERMISSION_REQUEST_CODE)
                }
            }

            // Support Geolocation Permissions in WebView
            override fun onGeolocationPermissionsShowPrompt(
                origin: String,
                callback: GeolocationPermissions.Callback
            ) {
                val hasLocationPermission = checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED
                if (hasLocationPermission) {
                    callback.invoke(origin, true, false)
                } else {
                    pendingGeolocationCallback = callback
                    pendingGeolocationOrigin = origin
                    requestPermissions(
                        arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION),
                        GEOLOCATION_REQUEST_CODE
                    )
                }
            }

            // Support File Chooser / Image Upload in WebView
            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                this@MainActivity.filePathCallback?.onReceiveValue(null)
                this@MainActivity.filePathCallback = filePathCallback

                val intent = fileChooserParams?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                    type = "*/*"
                    addCategory(Intent.CATEGORY_OPENABLE)
                }

                try {
                    startActivityForResult(intent, FILE_CHOOSER_REQUEST_CODE)
                } catch (e: Exception) {
                    this@MainActivity.filePathCallback?.onReceiveValue(null)
                    this@MainActivity.filePathCallback = null
                    return false
                }
                return true
            }
        }

        // Configure Back Button behavior (WebView back history traversal)
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                webView.evaluateJavascript(
                    "javascript:(function() {" +
                    "var m1 = document.querySelector('.modal-overlay:not(.hidden) .btn-close-modal');" +
                    "var m2 = document.querySelector('.modal[style*=\"block\"] .close-modal');" +
                    "var m3 = document.querySelector('.modal-overlay:not(.hidden) .btn-close');" +
                    "if (m1) { m1.click(); return 'MODAL_CLOSED'; }" +
                    "if (m2) { m2.click(); return 'MODAL_CLOSED'; }" +
                    "if (m3) { m3.click(); return 'MODAL_CLOSED'; }" +
                    "var sidebar = document.querySelector('#sidebar.open');" +
                    "var overlay = document.querySelector('#sidebar-overlay.active');" +
                    "if (sidebar && overlay) { overlay.click(); return 'SIDEBAR_CLOSED'; }" +
                    "return 'NO_MODAL'; })()"
                ) { result ->
                    if (result == "\"MODAL_CLOSED\"" || result == "\"SIDEBAR_CLOSED\"") {
                        // Handled by JS
                    } else if (webView.canGoBack()) {
                        webView.goBack()
                    } else {
                        isEnabled = false
                        this@MainActivity.onBackPressedDispatcher.onBackPressed()
                        isEnabled = true // Re-enable in case activity isn't destroyed
                    }
                }
            }
        })

        // Load the initial web app URL
        webView.loadUrl(TARGET_URL)

        // Initialize Notifications
        createNotificationChannel()
        loadNotifiedRequests()
        requestNotificationPermission()
        handleNotificationIntent(intent)
        startPolling()
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        when (requestCode) {
            PERMISSION_REQUEST_CODE -> {
                pendingPermissionRequest?.let { request ->
                    val grantedResources = mutableListOf<String>()
                    if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                        grantedResources.add(PermissionRequest.RESOURCE_VIDEO_CAPTURE)
                    }
                    if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
                        grantedResources.add(PermissionRequest.RESOURCE_AUDIO_CAPTURE)
                    }
                    request.grant(grantedResources.toTypedArray())
                    pendingPermissionRequest = null
                }
            }
            GEOLOCATION_REQUEST_CODE -> {
                pendingGeolocationCallback?.let { callback ->
                    val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
                    callback.invoke(pendingGeolocationOrigin ?: "", granted, false)
                    pendingGeolocationCallback = null
                    pendingGeolocationOrigin = null
                }
            }
            NOTIFICATION_PERMISSION_REQUEST_CODE -> {
                val granted = grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED
                if (granted) {
                    startPolling()
                }
            }
        }
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        if (requestCode == FILE_CHOOSER_REQUEST_CODE) {
            if (filePathCallback == null) return
            val results = WebChromeClient.FileChooserParams.parseResult(resultCode, data)
            filePathCallback?.onReceiveValue(results)
            filePathCallback = null
        }
    }

    override fun onNewIntent(intent: Intent?) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleNotificationIntent(intent)
    }

    override fun onDestroy() {
        stopPolling()
        super.onDestroy()
    }

    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                requestPermissions(
                    arrayOf(Manifest.permission.POST_NOTIFICATIONS),
                    NOTIFICATION_PERMISSION_REQUEST_CODE
                )
            }
        }
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channelName = "Gatekeeper Notifications"
            val channelDescription = "Notifications for student outpass biometric verification"
            val importance = NotificationManager.IMPORTANCE_HIGH
            val channel = NotificationChannel(CHANNEL_ID, channelName, importance).apply {
                description = channelDescription
                setSound(
                    RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION),
                    AudioAttributes.Builder()
                        .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                        .setUsage(AudioAttributes.USAGE_NOTIFICATION)
                        .build()
                )
            }
            val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    private fun startPolling() {
        if (isPolling) return
        isPolling = true
        pollingThread = Thread {
            while (isPolling) {
                try {
                    Thread.sleep(2000)
                    pollForUpdates()
                } catch (e: InterruptedException) {
                    break
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }
        }.apply {
            start()
        }
    }

    private fun stopPolling() {
        isPolling = false
        pollingThread?.interrupt()
        pollingThread = null
    }

    private fun pollForUpdates() {
        var connection: HttpURLConnection? = null
        try {
            val currentUrl = currentWebViewUrl
            android.util.Log.d("GatekeeperPoll", "pollForUpdates called. currentWebViewUrl: $currentUrl")
            val baseUrl = if (!currentUrl.isNullOrEmpty()) {
                try {
                    val parsed = URL(currentUrl)
                    "${parsed.protocol}://${parsed.authority}"
                } catch (e: Exception) {
                    TARGET_URL
                }
            } else {
                TARGET_URL
            }

            android.util.Log.d("GatekeeperPoll", "Resolved baseUrl: $baseUrl")

            val cookieManager = CookieManager.getInstance()
            val cookie = cookieManager.getCookie(baseUrl)
            if (cookie.isNullOrEmpty()) {
                android.util.Log.d("GatekeeperPoll", "Cookie is null or empty for $baseUrl. Returning...")
                return
            }

            android.util.Log.d("GatekeeperPoll", "Retrieving updates using cookie: $cookie")

            val url = URL("$baseUrl/api/dashboard/gatekeeper/updates/")
            connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            connection.connectTimeout = 3000
            connection.readTimeout = 3000
            connection.setRequestProperty("Cookie", cookie)
            connection.setRequestProperty("Accept", "application/json")

            val responseCode = connection.responseCode
            android.util.Log.d("GatekeeperPoll", "HTTP response code from updates endpoint: $responseCode")

            if (responseCode == HttpURLConnection.HTTP_OK) {
                val responseString = connection.inputStream.bufferedReader().use { it.readText() }
                android.util.Log.d("GatekeeperPoll", "Response string: $responseString")
                if (responseString.trim().startsWith("{")) {
                    val json = JSONObject(responseString)
                    if (json.optBoolean("success", false)) {
                        val requests = json.optJSONArray("requests") ?: return
                        android.util.Log.d("GatekeeperPoll", "Fetched ${requests.length()} requests")
                        for (i in 0 until requests.length()) {
                            val req = requests.getJSONObject(i)
                            val status = req.optString("request_status")
                            val requestId = req.optString("request_id")
                            android.util.Log.d("GatekeeperPoll", "Index $i: requestId=$requestId, status=$status")

                            if (status == "ACCEPTED" && requestId.isNotEmpty()) {
                                synchronized(notifiedRequests) {
                                    if (!notifiedRequests.contains(requestId)) {
                                        android.util.Log.d("GatekeeperPoll", "Request $requestId is ACCEPTED and not notified yet. Showing notification...")
                                        val studentName = req.optString("student_name")
                                        val studentId = req.optString("student_id")
                                        val hostelName = req.optString("hostel_name")
                                        val purpose = req.optString("outing_reason")
                                        val destination = req.optString("destination")
                                        val course = req.optString("course")
                                        val semester = req.optString("semester")
                                        val studentMobile = req.optString("student_mobile")
                                        val requestedExit = req.optString("requested_exit_datetime")
                                        val requestedEntry = req.optString("requested_entry_datetime")
                                        val parentConfirmed = req.optBoolean("parent_confirmed", false)
                                        val note = req.optString("note")

                                        showPushNotification(
                                            requestId = requestId,
                                            studentName = studentName,
                                            studentId = studentId,
                                            hostelName = hostelName,
                                            course = course,
                                            semester = semester,
                                            studentMobile = studentMobile,
                                            purpose = purpose,
                                            destination = destination,
                                            requestedExit = requestedExit,
                                            requestedEntry = requestedEntry,
                                            parentConfirmed = parentConfirmed,
                                            note = note
                                        )
                                        saveNotifiedRequest(requestId)
                                    } else {
                                        android.util.Log.d("GatekeeperPoll", "Request $requestId has already been notified.")
                                    }
                                }
                            }
                        }
                    }
                }
            } else {
                val errorString = connection.errorStream?.bufferedReader()?.use { it.readText() }
                android.util.Log.e("GatekeeperPoll", "Error response: $errorString")
            }
        } catch (e: Exception) {
            android.util.Log.e("GatekeeperPoll", "Error in pollForUpdates", e)
            e.printStackTrace()
        } finally {
            connection?.disconnect()
        }
    }

    private fun showPushNotification(
        requestId: String,
        studentName: String,
        studentId: String,
        hostelName: String,
        course: String,
        semester: String,
        studentMobile: String,
        purpose: String,
        destination: String,
        requestedExit: String,
        requestedEntry: String,
        parentConfirmed: Boolean,
        note: String
    ) {
        android.util.Log.d("GatekeeperPoll", "showPushNotification called for requestId=$requestId, student=$studentName")
        val notificationId = requestId.hashCode()

        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra("request_id", requestId)
        }

        val pendingIntent = PendingIntent.getActivity(
            this,
            notificationId,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        val title = "Outpass Verified - Grant OUT"

        val cleanExit = requestedExit.replace("T", " ").substringBefore("+")
        val cleanEntry = requestedEntry.replace("T", " ").substringBefore("+")

        val message = """
            Student: $studentName ($studentId)
            Hostel: $hostelName
            Course: $course (Sem $semester)
            Mobile: $studentMobile
            
            Request Details:
            - Purpose: $purpose
            - Destination: $destination
            - Exit Time: $cleanExit
            - Entry Time: $cleanEntry
            - Parent Confirmed: ${if (parentConfirmed) "Yes" else "No"}
            - Warden Remarks: ${if (note.isEmpty()) "None" else note}
            
            The student has successfully verified on the biometric device.
            The Gatekeeper should now grant OUT permission.
        """.trimIndent()

        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(title)
            .setContentText("Student $studentName ($studentId) verified. Grant OUT permission.")
            .setStyle(NotificationCompat.BigTextStyle().bigText(message))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setSound(RingtoneManager.getDefaultUri(RingtoneManager.TYPE_NOTIFICATION))
            .setContentIntent(pendingIntent)
            .setAutoCancel(true)

        val manager = getSystemService(NOTIFICATION_SERVICE) as NotificationManager

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val hasPermission = checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
            android.util.Log.d("GatekeeperPoll", "POST_NOTIFICATIONS permission granted: $hasPermission")
            if (!hasPermission) {
                return
            }
        }

        android.util.Log.d("GatekeeperPoll", "Notifying manager with ID $notificationId")
        manager.notify(notificationId, builder.build())
    }

    private fun loadNotifiedRequests() {
        val prefs = getSharedPreferences("gatekeeper_prefs", MODE_PRIVATE)
        val savedSet = prefs.getStringSet("notified_requests", null)
        if (savedSet != null) {
            notifiedRequests.addAll(savedSet)
        }
    }

    private fun saveNotifiedRequest(requestId: String) {
        notifiedRequests.add(requestId)
        val prefs = getSharedPreferences("gatekeeper_prefs", MODE_PRIVATE)
        prefs.edit().putStringSet("notified_requests", notifiedRequests).apply()
    }

    private fun handleNotificationIntent(intent: Intent?) {
        val requestId = intent?.getStringExtra("request_id") ?: return
        pendingRequestId = requestId
        webView.evaluateJavascript("javascript:if(typeof window.openRequestDetails !== 'undefined') { window.openRequestDetails('$requestId'); 'SUCCESS'; } else { 'FAILED'; }") { result ->
            if (result == "\"SUCCESS\"") {
                pendingRequestId = null
            }
        }
    }

    inner class WebAppInterface {
        @JavascriptInterface
        fun setSwipeRefreshEnabled(enabled: Boolean) {
            runOnUiThread {
                swipeRefresh.isEnabled = enabled
            }
        }
    }
}
