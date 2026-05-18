(function () {
    "use strict";

    var wp = window.FDP_WORKPLACE;
    var active = window.FDP_ACTIVE;

    var center = active ? [active.lat, active.lon] : [wp.lat, wp.lon];
    var map = L.map("map").setView(center, 9);

    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap"
    }).addTo(map);

    // Marker sede aziendale (sempre presente)
    L.marker([wp.lat, wp.lon], {title: wp.name})
        .bindPopup("<b>" + wp.name + "</b>")
        .addTo(map);

    if (active) {
        L.marker([active.lat, active.lon], {title: active.label})
            .bindPopup("<b>" + active.label + "</b>")
            .addTo(map);
    } else {
        // Click handler per scegliere un punto
        var pickedMarker = null;
        map.on("click", function (e) {
            var lat = e.latlng.lat;
            var lon = e.latlng.lng;

            if (pickedMarker) {
                map.removeLayer(pickedMarker);
            }
            pickedMarker = L.marker([lat, lon]).addTo(map);

            document.getElementById("input-lat").value = lat.toFixed(6);
            document.getElementById("input-lon").value = lon.toFixed(6);
            document.getElementById("display-coords").textContent =
                lat.toFixed(6) + ", " + lon.toFixed(6);
            document.getElementById("display-address").textContent = "(caricamento...)";
            document.getElementById("save-form").style.display = "block";

            // Reverse geocoding via Nominatim (lato browser, no proxy server)
            var url = "https://nominatim.openstreetmap.org/reverse?format=json&lat="
                + lat + "&lon=" + lon + "&zoom=18&addressdetails=1";
            fetch(url, {headers: {"Accept": "application/json"}})
                .then(function (r) { return r.json(); })
                .then(function (data) {
                    var addr = (data && data.display_name) || "(indirizzo non trovato)";
                    document.getElementById("display-address").textContent = addr;
                    var labelInput = document.getElementById("input-label");
                    if (!labelInput.value) {
                        labelInput.value = addr.substring(0, 200);
                    }
                })
                .catch(function () {
                    document.getElementById("display-address").textContent = "(errore reverse-geocoding)";
                });
        });
    }
}());
