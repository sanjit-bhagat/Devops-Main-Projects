document.addEventListener("DOMContentLoaded", function () {
    console.log("✅ main.js loaded");

    // Get GeoJSON from hidden script tag
    const geojsonData = JSON.parse(
        document.getElementById("geojson-data").textContent
    );

    // Get coordinates safely from HTML data attributes
    const mapDiv = document.getElementById("map");
    const centerLat = Number(mapDiv.dataset.lat);
    const centerLon = Number(mapDiv.dataset.lon);

    // Initialize map
    const map = L.map("map").setView([centerLat, centerLon], 13);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "© OpenStreetMap"
    }).addTo(map);

    // Add GeoJSON
    const layer = L.geoJSON(geojsonData, {
        style: {
            color: "green",
            fillColor: "lightgreen",
            fillOpacity: 0.5,
            weight: 2
        },
        onEachFeature: function (feature, layer) {
            const name = feature.properties.name || "Area";
            const trees = feature.properties.trees || 0;
            layer.bindPopup(
                `<b>${name}</b><br>Estimated Trees: ${trees}`
            );
        }
    }).addTo(map);

    map.fitBounds(layer.getBounds());
});
