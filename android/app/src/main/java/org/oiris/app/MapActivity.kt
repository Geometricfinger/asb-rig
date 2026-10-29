package org.oiris.app

import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import androidx.fragment.app.FragmentActivity
import org.mapsforge.core.model.LatLong
import org.mapsforge.map.android.graphics.AndroidGraphicFactory
import org.mapsforge.map.android.util.AndroidUtil
import org.mapsforge.map.android.view.MapView
import org.mapsforge.map.layer.overlay.Marker
import org.mapsforge.map.layer.renderer.TileRendererLayer
import org.mapsforge.map.reader.MapFile
import org.mapsforge.map.rendertheme.InternalRenderTheme
import java.io.File

/** P4/P9 offline sighting map (Mapsforge, offline .map file only; the app has no INTERNET permission).
 *  Put an OpenStreetMap-derived .map file in Android/data/org.oiris.app/files/maps/. Pins come from
 *  the encrypted SightingStore (rounded display); attribution is always shown. */
class MapActivity : FragmentActivity() {
    private var mapView: MapView? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
        AndroidGraphicFactory.createInstance(application)
        val root = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
        val attribution = TextView(this).apply { text = getString(R.string.osm_attribution); setTextColor(Color.LTGRAY); setPadding(16, 8, 16, 8) }
        val mapFile = File(getExternalFilesDir("maps"), "").listFiles { f -> f.extension == "map" }?.firstOrNull()
        if (mapFile == null) {
            root.addView(TextView(this).apply { text = getString(R.string.map_missing); setPadding(32, 48, 32, 32) })
        } else {
            val mv = MapView(this).also { mapView = it }
            mv.isClickable = true
            mv.mapScaleBar.isVisible = true
            val cache = AndroidUtil.createTileCache(this, "mapcache", mv.model.displayModel.tileSize, 1f, mv.model.frameBufferModel.overdrawFactor)
            val store = MapFile(mapFile)
            val layer = TileRendererLayer(cache, store, mv.model.mapViewPosition, AndroidGraphicFactory.INSTANCE)
            layer.setXmlRenderTheme(InternalRenderTheme.DEFAULT)
            mv.layerManager.layers.add(layer)
            val pins = SessionKeys.store?.pins().orEmpty()
            val dot = GradientDrawable().apply { shape = GradientDrawable.OVAL; setColor(Color.WHITE); setStroke(4, Color.BLACK); setSize(28, 28) }
            val bmp = AndroidGraphicFactory.convertToBitmap(dot)
            pins.forEach { mv.layerManager.layers.add(Marker(LatLong(it.lat, it.lon), bmp, 0, 0)) }
            val centre = pins.lastOrNull()?.let { LatLong(it.lat, it.lon) } ?: store.startPosition() ?: store.boundingBox().centerPoint
            mv.setCenter(centre); mv.setZoomLevel(if (pins.isEmpty()) 12 else 15)
            root.addView(mv, LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1f))
            if (pins.isEmpty()) attribution.text = "${getString(R.string.osm_attribution)} · ${getString(R.string.map_no_pins)}"
        }
        root.addView(attribution)
        setContentView(root)
    }

    override fun onDestroy() { mapView?.destroyAll(); AndroidGraphicFactory.clearResourceMemoryCache(); super.onDestroy() }
}
