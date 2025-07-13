const map = L.map('map', {
    center: [-15.8402, -70.0219],
    zoom: 13,
    maxZoom: 18
});

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap contributors'
}).addTo(map);

const paraderosClusterGroup = L.markerClusterGroup({
    disableClusteringAtZoom: 18
});

map.addLayer(paraderosClusterGroup);

function cargarParaderos() {
    fetch('/api/paraderos/')
        .then(res => res.json())
        .then(data => {
            data.paraderos.forEach(paradero => {
                const marker = L.marker([paradero.lat, paradero.lng])
                    .bindPopup(`Paradero ${paradero.orden}: ${paradero.nombre}`)
                    .on('click', () => obtenerInfoParadero(paradero.id));
                paraderosClusterGroup.addLayer(marker);
            });
        });
}

function obtenerInfoParadero(paraderoId) {
    fetch(`/api/paradero-info/${paraderoId}/`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert(`🚌 Bus más cercano: ${data.bus.nombre}\n🕒 Tiempo estimado: ${data.tiempo_minutos} min`);
            } else {
                alert(data.message || 'No se pudo determinar un bus cercano.');
            }
        })
        .catch(err => {
            console.error("Error al obtener info de paradero:", err);
        });
}

cargarParaderos();
