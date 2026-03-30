let map;
let markers = [];

const KOCAELI_CENTER = { lat: 40.7654, lng: 29.9408 };

const KOCAELI_BOUNDS = {
    north: 41.2,
    south: 40.5,
    west: 29.3,
    east: 30.4,
};

const markerIcons = {
    "Trafik Kazası": "/static/icons/kaza.jpg",
    "Yangın": "/static/icons/yangin.jpg",
    "Elektrik Kesintisi": "/static/icons/elektrik.jpg",
    "Hırsızlık": "/static/icons/hirsizlik.jpg",
    "Kültürel Etkinlikler": "/static/icons/kultur.jpg",
};

function initMap() {
    map = new google.maps.Map(document.getElementById("map"), {
        center: KOCAELI_CENTER,
        zoom: 10,
        restriction: {
            latLngBounds: KOCAELI_BOUNDS,
            strictBounds: true,
        },
    });

    bindEvents();
    loadFilters();
    loadNews();
}

function bindEvents() {
    document.getElementById("applyFilters").addEventListener("click", () => {
        loadNews();
    });

    document.getElementById("clearFilters").addEventListener("click", () => {
        document.getElementById("newsType").value = "";
        document.getElementById("district").value = "";
        document.getElementById("startDate").value = "";
        document.getElementById("endDate").value = "";
        loadNews();
    });
}

async function loadFilters() {
    const response = await fetch("/filters");
    const data = await response.json();

    const newsTypeSelect = document.getElementById("newsType");
    const districtSelect = document.getElementById("district");

    newsTypeSelect.innerHTML = '<option value="">Tümü</option>';
    districtSelect.innerHTML = '<option value="">Tümü</option>';

    data.news_types.forEach((item) => {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = item;
        newsTypeSelect.appendChild(option);
    });

    data.districts.forEach((item) => {
        const option = document.createElement("option");
        option.value = item;
        option.textContent = item;
        districtSelect.appendChild(option);
    });
}

function buildQueryString() {
    const newsType = document.getElementById("newsType").value;
    const district = document.getElementById("district").value;
    const startDate = document.getElementById("startDate").value;
    const endDate = document.getElementById("endDate").value;

    const params = new URLSearchParams();

    if (newsType) params.append("news_type", newsType);
    if (district) params.append("district", district);
    if (startDate) params.append("start_date", startDate);
    if (endDate) params.append("end_date", endDate);

    return params.toString();
}

async function loadNews() {
    const query = buildQueryString();
    const url = query ? `/news?${query}` : "/news";

    const response = await fetch(url);
    const data = await response.json();

    updateStats(data);
    renderNewsList(data.all_items || []);
    renderMarkers(data.items || []);
}

function updateStats(data) {
    const stats = document.getElementById("stats");
    stats.innerHTML = `
        <div>Toplam kayıt: <strong>${data.total_count ?? 0}</strong></div>
        <div>Haritada gösterilen: <strong>${data.map_count ?? 0}</strong></div>
    `;
}

function renderNewsList(items) {
    const newsList = document.getElementById("newsList");
    newsList.innerHTML = "";

    if (!items.length) {
        newsList.innerHTML = "<p>Filtreye uygun haber bulunamadı.</p>";
        return;
    }

    items.slice(0, 20).forEach((item) => {
        const card = document.createElement("div");
        card.className = "news-card";

        card.innerHTML = `
            <h3>${escapeHtml(item.title)}</h3>
            <div class="news-meta">
                ${escapeHtml(item.news_type || "-")} |
                ${escapeHtml(item.publish_date || "-")} |
                ${escapeHtml(item.district || "-")}
            </div>
            <div class="news-meta">
                Kaynak: ${escapeHtml(item.source?.site_name || "-")}
            </div>
            <a href="${item.source?.url || "#"}" target="_blank" rel="noopener noreferrer">Habere Git</a>
        `;

        newsList.appendChild(card);
    });
}

function clearMarkers() {
    markers.forEach((marker) => marker.setMap(null));
    markers = [];
}

function getOffsetPosition(latNum, lngNum, offsetIndex) {
    if (offsetIndex === 0) {
        return { lat: latNum, lng: lngNum };
    }

    // 700 metre baz yarıçap
    const distanceMeters = 700;

    const latStep = distanceMeters / 111320;
    const lngStep = distanceMeters / (111320 * Math.cos(latNum * Math.PI / 180));

    const pointsPerRing = 8;
    const ring = Math.floor((offsetIndex - 1) / pointsPerRing) + 1;
    const indexInRing = (offsetIndex - 1) % pointsPerRing;

    const angle = (indexInRing / pointsPerRing) * 2 * Math.PI;

    return {
        lat: latNum + Math.sin(angle) * latStep * ring,
        lng: lngNum + Math.cos(angle) * lngStep * ring,
    };
}

function renderMarkers(items) {
    clearMarkers();

    const bounds = new google.maps.LatLngBounds();
    let hasMarker = false;

    // Aynı koordinatta birden fazla haber varsa küçük offset uygula
    const coordinateCount = {};

    items.forEach((item) => {
        const lat = item.coordinates?.lat;
        const lng = item.coordinates?.lng;

        if (
            lat === null || lat === undefined || lat === "" ||
            lng === null || lng === undefined || lng === ""
        ) {
            return;
        }

        const latNum = Number(lat);
        const lngNum = Number(lng);

        if (Number.isNaN(latNum) || Number.isNaN(lngNum)) {
            return;
        }

        const key = `${latNum.toFixed(5)}_${lngNum.toFixed(5)}`;

        if (!coordinateCount[key]) {
            coordinateCount[key] = 0;
        }

        const offsetIndex = coordinateCount[key];
        coordinateCount[key] += 1;

        const position = getOffsetPosition(latNum, lngNum, offsetIndex);

        const marker = new google.maps.Marker({
            position,
            map,
            title: item.title,
            icon: {
                url: markerIcons[item.news_type] || "/static/icons/kaza.jpg",
                scaledSize: new google.maps.Size(28, 28),
            },
        });

        const infoWindow = new google.maps.InfoWindow({
            content: `
                <div style="max-width: 260px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 16px;">
                        ${escapeHtml(item.title)}
                    </h3>
                    <p style="margin: 0 0 6px 0;"><strong>Tarih:</strong> ${escapeHtml(item.publish_date || "-")}</p>
                    <p style="margin: 0 0 6px 0;"><strong>Kaynak:</strong> ${escapeHtml(item.source?.site_name || "-")}</p>
                    <p style="margin: 0;">
                        <a href="${item.source?.url || "#"}" target="_blank" rel="noopener noreferrer">
                            Habere Git
                        </a>
                    </p>
                </div>
            `,
        });

        marker.addListener("click", () => {
            infoWindow.open({
                anchor: marker,
                map,
            });
        });

        markers.push(marker);
        bounds.extend(position);
        hasMarker = true;
    });

    if (hasMarker) {
        map.fitBounds(bounds);

        google.maps.event.addListenerOnce(map, "idle", function () {
            if (map.getZoom() > 13) {
                map.setZoom(13);
            }
        });
    } else {
        map.setCenter(KOCAELI_CENTER);
        map.setZoom(10);
    }
}

function escapeHtml(value) {
    if (!value) return "";
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}
