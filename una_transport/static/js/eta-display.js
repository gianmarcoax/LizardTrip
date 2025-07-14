/**
 * Componente para mostrar información de tiempo estimado de llegada (ETA)
 * de buses en el frontend de LizardTrip
 */

class ETADisplay {
    constructor() {
        this.updateInterval = 30000; // Actualizar cada 30 segundos
        this.busMarkers = {};
        this.etaInfoWindow = null;
        this.isInitialized = false;
    }

    /**
     * Inicializa el componente ETA
     */
    init() {
        if (this.isInitialized) return;
        console.log('🚌 Inicializando sistema ETA...');
        // Crear panel de información ETA
        this.createETAPanel();
        // Crear panel de ubicación de usuario
        this.createUserLocationPanel();
        // Iniciar actualizaciones automáticas
        this.startAutoUpdate();
        // Actualización inicial
        this.updateETAInfo();
        this.isInitialized = true;
    }

    /**
     * Crea el panel de información ETA (fijo, ocultable)
     */
    createETAPanel() {
        // Crear contenedor del panel ETA
        const etaPanel = document.createElement('div');
        etaPanel.id = 'eta-panel';
        etaPanel.className = 'eta-panel';
        etaPanel.innerHTML = `
            <div class="eta-header">
                <h3>🚌 Información de Buses</h3>
                <button id="eta-hide-btn" class="eta-hide-btn">➖</button>
                <button id="eta-refresh-btn" class="eta-refresh-btn">🔄</button>
            </div>
            <div id="eta-content" class="eta-content">
                <div class="eta-loading">Cargando información...</div>
            </div>
        `;
        this.addETAStyles();
        document.body.appendChild(etaPanel);
        document.getElementById('eta-refresh-btn').addEventListener('click', () => {
            this.updateETAInfo();
        });
        document.getElementById('eta-hide-btn').addEventListener('click', () => {
            this.hidePanel();
        });
    }

    /**
     * Crea el panel de ubicación de usuario debajo del panel ETA
     */
    createUserLocationPanel() {
        const userPanel = document.createElement('div');
        userPanel.id = 'user-location-panel';
        userPanel.className = 'eta-panel';
        userPanel.style.marginTop = '16px';
        userPanel.innerHTML = `
            <div class="eta-header">
                <h3>📍 Mi Ubicación y Ruta</h3>
                <button id="user-location-hide-btn" class="eta-hide-btn">➖</button>
            </div>
            <div id="user-location-content" class="eta-content">
                <div style="margin-bottom: 10px;">
                    <button id="share-location-btn" class="eta-refresh-btn">Compartir ubicación</button>
                </div>
                <div style="margin-bottom: 10px;">
                    <label><input type="radio" name="user-orientacion" value="ida" checked> Ida (U → Dante Nava)</label>
                    <label style="margin-left: 12px;"><input type="radio" name="user-orientacion" value="vuelta"> Vuelta (Dante Nava → U)</label>
                </div>
                <div id="user-location-status" class="eta-loading">Ubicación no compartida</div>
                <div id="user-location-route-info" style="margin-top:10px;"></div>
            </div>
        `;
        document.body.appendChild(userPanel);
        // Ocultar panel
        document.getElementById('user-location-hide-btn').addEventListener('click', () => {
            userPanel.style.display = 'none';
            let showBtn = document.getElementById('user-location-show-btn');
            if (!showBtn) {
                showBtn = document.createElement('button');
                showBtn.id = 'user-location-show-btn';
                showBtn.className = 'eta-show-btn';
                showBtn.style.top = '570px';
                showBtn.innerHTML = '📍';
                showBtn.title = 'Mostrar panel de ubicación';
                showBtn.onclick = () => {
                    userPanel.style.display = 'block';
                    showBtn.style.display = 'none';
                };
                document.body.appendChild(showBtn);
            } else {
                showBtn.style.display = 'block';
            }
        });
        // Compartir ubicación
        document.getElementById('share-location-btn').addEventListener('click', () => {
            this.shareUserLocation();
        });
        // Cambiar orientación
        const radios = userPanel.querySelectorAll('input[name="user-orientacion"]');
        radios.forEach(radio => {
            radio.addEventListener('change', () => {
                this.userOrientation = radio.value;
                if (this.userLat && this.userLng) {
                    this.findAndShowWalkingRoute();
                }
            });
        });
        // Estado inicial
        this.userOrientation = 'ida';
        this.userLat = null;
        this.userLng = null;
        this.userLocationMarker = null;
        this.userRoutePolyline = null;
    }

    /**
     * Oculta el panel ETA y muestra un botón flotante para mostrarlo
     */
    hidePanel() {
        const etaPanel = document.getElementById('eta-panel');
        if (etaPanel) etaPanel.style.display = 'none';
        let showBtn = document.getElementById('eta-show-btn');
        if (!showBtn) {
            showBtn = document.createElement('button');
            showBtn.id = 'eta-show-btn';
            showBtn.className = 'eta-show-btn';
            showBtn.innerHTML = '🚌';
            showBtn.title = 'Mostrar información de buses';
            showBtn.onclick = () => {
                etaPanel.style.display = 'block';
                showBtn.style.display = 'none';
            };
            document.body.appendChild(showBtn);
        } else {
            showBtn.style.display = 'block';
        }
    }

    /**
     * Agrega estilos CSS para el panel ETA (fijo, responsivo, ocultable)
     */
    addETAStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .eta-panel {
                position: absolute;
                top: 110px;
                left: 20px;
                width: 340px;
                max-width: 95vw;
                max-height: 420px;
                background: white;
                border-radius: 14px;
                box-shadow: 0 6px 24px rgba(0,0,0,0.18);
                z-index: 500;
                font-family: 'Segoe UI', Arial, sans-serif;
                overflow: hidden;
                border: 1.5px solid #e0e0e0;
                transition: box-shadow 0.2s, top 0.2s;
                margin-bottom: 12px;
            }
            #user-location-panel.eta-panel {
                top: 540px;
                left: 20px;
                margin-top: 0;
                box-shadow: 0 4px 18px rgba(0,0,0,0.13);
            }
            .eta-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 14px;
                background: linear-gradient(90deg, #e3f0ff 0%, #f8f9fa 100%);
                border-bottom: 1px solid #e0e0e0;
            }
            .eta-header h3 {
                margin: 0;
                font-size: 16px;
                color: #1a237e;
                flex: 1;
                font-weight: 600;
                letter-spacing: 0.5px;
            }
            .eta-refresh-btn, .eta-hide-btn {
                background: #f1f3f4;
                border: none;
                font-size: 18px;
                cursor: pointer;
                padding: 4px 7px;
                border-radius: 6px;
                margin-left: 2px;
                transition: background-color 0.2s, box-shadow 0.2s;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            }
            .eta-refresh-btn:hover, .eta-hide-btn:hover {
                background-color: #e3eafc;
            }
            .eta-content {
                max-height: 320px;
                overflow-y: auto;
                padding: 0 2px 8px 2px;
            }
            .eta-loading {
                padding: 16px;
                text-align: center;
                color: #666;
            }
            .eta-bus-item {
                padding: 10px 14px;
                border-bottom: 1px solid #f2f2f2;
                transition: background-color 0.2s;
                border-radius: 7px;
                margin: 4px 0;
                background: #f8fbff;
            }
            .eta-bus-item:hover {
                background-color: #e3f0ff;
            }
            .eta-bus-item:last-child {
                border-bottom: none;
            }
            .eta-bus-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 2px;
            }
            .eta-bus-name {
                font-weight: bold;
                color: #333;
                font-size: 14px;
            }
            .eta-orientacion {
                font-size: 13px;
                display: flex;
                align-items: center;
                gap: 4px;
            }
            .eta-orientacion-icono {
                font-size: 16px;
            }
            .eta-orientacion-texto {
                font-size: 13px;
                color: #555;
            }
            .eta-bus-info {
                font-size: 12px;
                color: #666;
                line-height: 1.4;
            }
            .eta-paradero-info {
                margin-top: 2px;
                font-size: 11.5px;
                color: #888;
            }
            .eta-error {
                padding: 14px;
                color: #721c24;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
                border-radius: 4px;
                margin: 8px;
            }
            .eta-empty {
                padding: 16px;
                text-align: center;
                color: #666;
                font-style: italic;
            }
            .eta-show-btn {
                position: fixed;
                left: 20px;
                z-index: 500;
                background: #007bff;
                color: white;
                border: none;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                font-size: 22px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.15);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.2s, top 0.2s;
            }
            .eta-show-btn:hover {
                background: #0056b3;
            }
            #eta-show-btn {
                top: 130px;
            }
            #user-location-show-btn {
                top: 540px;
            }
            /* Panel de usuario: estilos extra */
            #user-location-panel .eta-header {
                background: linear-gradient(90deg, #fffbe3 0%, #f8f9fa 100%);
            }
            #user-location-panel .eta-header h3 {
                color: #b26a00;
            }
            #user-location-panel .eta-content {
                background: #fffefb;
            }
            #user-location-panel label {
                font-size: 13px;
                color: #444;
                margin-right: 0;
                margin-left: 0;
                margin-bottom: 0;
                font-weight: 500;
            }
            #user-location-panel input[type="radio"] {
                accent-color: #007bff;
                margin-right: 3px;
            }
            #share-location-btn {
                font-size: 14px;
                padding: 5px 10px;
                margin: 0 2px;
                border-radius: 6px;
                background: #e3f0ff;
                color: #1a237e;
                border: 1px solid #b6d4fe;
                font-weight: 500;
                transition: background 0.2s, color 0.2s;
            }
            #share-location-btn:hover {
                background: #b6d4fe;
                color: #0d1a4d;
            }
            #user-location-status {
                font-size: 12.5px;
                color: #007bff;
                margin-bottom: 2px;
            }
            #user-location-route-info {
                font-size: 12.5px;
                color: #333;
                background: #f3f8ff;
                border-radius: 6px;
                padding: 6px 8px;
                margin-top: 6px;
                margin-bottom: 2px;
                box-shadow: 0 1px 2px rgba(0,0,0,0.04);
            }
            @media (max-width: 768px) {
                .eta-panel {
                    width: 98vw;
                    left: 1vw;
                    right: 1vw;
                    top: 56px;
                    max-width: 100vw;
                }
                #user-location-panel.eta-panel {
                    top: calc(56px + 440px + 10px);
                    left: 1vw;
                }
                .eta-show-btn {
                    left: 8px;
                }
                #eta-show-btn {
                    top: 120px;
                }
                #user-location-show-btn {
                    top: calc(56px + 440px + 10px);
                }
            }
        `;
        document.head.appendChild(style);
    }

    /**
     * Hace el panel arrastrable
     */
    makePanelDraggable(panel) {
        let isDragging = false;
        let currentX;
        let currentY;
        let initialX;
        let initialY;
        let xOffset = 0;
        let yOffset = 0;

        panel.addEventListener('mousedown', dragStart);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', dragEnd);

        function dragStart(e) {
            if (e.target.closest('.eta-header')) {
                initialX = e.clientX - xOffset;
                initialY = e.clientY - yOffset;
                isDragging = true;
            }
        }

        function drag(e) {
            if (isDragging) {
                e.preventDefault();
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;
                xOffset = currentX;
                yOffset = currentY;
                setTranslate(currentX, currentY, panel);
            }
        }

        function dragEnd() {
            isDragging = false;
        }

        function setTranslate(xPos, yPos, el) {
            el.style.transform = `translate3d(${xPos}px, ${yPos}px, 0)`;
        }
    }

    /**
     * Actualiza la información de ETA usando la nueva API
     */
    async updateETAInfo() {
        try {
            const response = await fetch('/api/buses-next-stop/');
            const data = await response.json();
            this.displayETAInfo(data.buses);
        } catch (error) {
            console.error('Error al obtener información ETA:', error);
            this.displayError('Error al cargar información de buses');
        }
    }

    /**
     * Muestra la información de ETA en el panel (nueva API)
     */
    displayETAInfo(buses) {
        const content = document.getElementById('eta-content');
        if (!buses || buses.length === 0) {
            content.innerHTML = `
                <div class="eta-empty">
                    No hay buses activos en este momento
                </div>
            `;
            return;
        }
        let html = '';
        buses.forEach(bus => {
            let orientacion = '';
            if (bus.orientacion) {
                orientacion = `<span class='eta-orientacion-icono'>${bus.orientacion_icono || ''}</span> <span class='eta-orientacion-texto'>${bus.orientacion === 'ida' ? 'Ida' : 'Vuelta'}</span>`;
            }
            let paraderoInfo = '';
            if (bus.proximo_paradero) {
                paraderoInfo = `<div class="eta-paradero-info">📍 Próximo: ${bus.proximo_paradero.nombre}</div>`;
            } else {
                paraderoInfo = `<div class="eta-paradero-info">Sin próximo paradero</div>`;
            }
            // Quitar ETA
            html += `
                <div class="eta-bus-item" data-bus-id="${bus.bus_id}">
                    <div class="eta-bus-header">
                        <div class="eta-bus-name">${bus.nombre}</div>
                        <div class="eta-orientacion">${orientacion}</div>
                    </div>
                    <div class="eta-bus-info">
                        <div>🛣️ ${bus.ruta || ''}</div>
                        ${paraderoInfo}
                    </div>
                </div>
            `;
        });
        content.innerHTML = html;
        this.addBusItemEvents();
    }

    /**
     * Agrega eventos a los elementos de bus
     */
    addBusItemEvents() {
        const busItems = document.querySelectorAll('.eta-bus-item');
        
        busItems.forEach(item => {
            item.addEventListener('click', () => {
                const busId = item.dataset.busId;
                this.showBusDetails(busId);
            });
        });
    }

    /**
     * Muestra información detallada de un bus específico
     */
    async showBusDetails(busId) {
        try {
            // Solo mostrar nombre del bus y próximo paradero, sin ETA ni errores
            const busItem = document.querySelector(`[data-bus-id="${busId}"]`);
            const busName = busItem.querySelector('.eta-bus-name').textContent;
            const paraderoInfo = busItem.querySelector('.eta-paradero-info')?.textContent || '';
            alert(`Bus: ${busName}\n${paraderoInfo}`);
        } catch (error) {
            // No mostrar ningún error al usuario
        }
    }

    /**
     * Muestra un mensaje de error
     */
    displayError(message) {
        const content = document.getElementById('eta-content');
        content.innerHTML = `
            <div class="eta-error">
                ❌ ${message}
            </div>
        `;
    }

    /**
     * Inicia las actualizaciones automáticas
     */
    startAutoUpdate() {
        setInterval(() => {
            this.updateETAInfo();
        }, this.updateInterval);
    }

    /**
     * Detiene las actualizaciones automáticas
     */
    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
    }

    /**
     * Obtiene información de ETA para un paradero específico
     */
    async getParaderoETA(paraderoId) {
        try {
            const response = await fetch(`/api/paradero-eta/${paraderoId}/`);
            const data = await response.json();
            return data;
        } catch (error) {
            console.error('Error al obtener ETA del paradero:', error);
            return null;
        }
    }

    /**
     * Solicita la ubicación del usuario y la muestra en el mapa
     */
    shareUserLocation() {
        const status = document.getElementById('user-location-status');
        if (!navigator.geolocation) {
            status.textContent = 'Geolocalización no soportada';
            return;
        }
        status.textContent = 'Obteniendo ubicación...';
        navigator.geolocation.getCurrentPosition(
            (pos) => {
                this.userLat = pos.coords.latitude;
                this.userLng = pos.coords.longitude;
                status.textContent = `Ubicación compartida: (${this.userLat.toFixed(5)}, ${this.userLng.toFixed(5)})`;
                this.showUserLocationOnMap();
                this.findAndShowWalkingRoute();
            },
            (err) => {
                status.textContent = 'No se pudo obtener la ubicación';
            },
            { enableHighAccuracy: true }
        );
    }

    /**
     * Muestra la ubicación del usuario en el mapa (requiere integración con el mapa global)
     */
    showUserLocationOnMap() {
        if (window.map && this.userLat && this.userLng) {
            if (this.userLocationMarker) {
                this.userLocationMarker.setMap(null);
            }
            this.userLocationMarker = new google.maps.Marker({
                position: { lat: this.userLat, lng: this.userLng },
                map: window.map,
                icon: {
                    path: google.maps.SymbolPath.CIRCLE,
                    scale: 8,
                    fillColor: '#007bff',
                    fillOpacity: 1,
                    strokeColor: '#fff',
                    strokeWeight: 2
                },
                title: 'Tu ubicación'
            });
        }
    }

    /**
     * Busca el paradero más cercano según la orientación y muestra la ruta caminando usando OSRM
     */
    async findAndShowWalkingRoute() {
        const routeInfo = document.getElementById('user-location-route-info');
        routeInfo.textContent = 'Buscando paradero más cercano...';
        // Obtener paraderos de la orientación seleccionada
        let paraderos = await this.fetchParaderosByOrientation(this.userOrientation);
        if (!paraderos || paraderos.length === 0) {
            routeInfo.textContent = 'No se encontraron paraderos.';
            return;
        }
        // Buscar el paradero más cercano
        let minDist = Infinity;
        let closest = null;
        paraderos.forEach(p => {
            const dist = this.haversineDistance(this.userLat, this.userLng, p.lat, p.lng);
            if (dist < minDist) {
                minDist = dist;
                closest = p;
            }
        });
        if (!closest) {
            routeInfo.textContent = 'No se encontró paradero cercano.';
            return;
        }
        // Mostrar info
        routeInfo.innerHTML = `Paradero más cercano: <b>${closest.nombre}</b> (${minDist.toFixed(0)} m)`;
        // Pedir ruta a OSRM
        const osrmUrl = `https://router.project-osrm.org/route/v1/foot/${this.userLng},${this.userLat};${closest.lng},${closest.lat}?overview=full&geometries=geojson`;
        try {
            const resp = await fetch(osrmUrl);
            const data = await resp.json();
            if (data.routes && data.routes.length > 0) {
                const coords = data.routes[0].geometry.coordinates;
                this.drawUserRouteOnMap(coords);
            } else {
                routeInfo.innerHTML += '<br>No se pudo calcular la ruta caminando.';
            }
        } catch (e) {
            routeInfo.innerHTML += '<br>Error al consultar OSRM.';
        }
    }

    /**
     * Dibuja la ruta caminando en el mapa (requiere integración con el mapa global)
     */
    drawUserRouteOnMap(coords) {
        if (window.map && window.google && coords && coords.length > 1) {
            if (this.userRoutePolyline) {
                this.userRoutePolyline.setMap(null);
            }
            const path = coords.map(c => ({ lat: c[1], lng: c[0] }));
            this.userRoutePolyline = new google.maps.Polyline({
                path: path,
                geodesic: true,
                strokeColor: '#28a745',
                strokeOpacity: 0.9,
                strokeWeight: 5,
                map: window.map
            });
        }
    }

    /**
     * Obtiene los paraderos de la orientación seleccionada
     */
    async fetchParaderosByOrientation(orientacion) {
        try {
            const resp = await fetch('/api/paraderos/');
            const data = await resp.json();
            return data.paraderos.filter(p => p.orientacion === orientacion);
        } catch (e) {
            return [];
        }
    }

    /**
     * Calcula la distancia Haversine en metros
     */
    haversineDistance(lat1, lng1, lat2, lng2) {
        function toRad(x) { return x * Math.PI / 180; }
        const R = 6371000; // Radio de la tierra en metros
        const dLat = toRad(lat2 - lat1);
        const dLng = toRad(lng2 - lng1);
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) *
                  Math.sin(dLng/2) * Math.sin(dLng/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }

    /**
     * Destruye el componente
     */
    destroy() {
        this.stopAutoUpdate();
        const panel = document.getElementById('eta-panel');
        if (panel) {
            panel.remove();
        }
        this.isInitialized = false;
    }
}

// Exportar para uso global
window.ETADisplay = ETADisplay; 