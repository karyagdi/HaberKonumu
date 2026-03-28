let map;
let markers = [];

const KOCAELI_CENTER = { lat: 40.7654, lng: 29.9408 };

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
    renderNewsList(data.all_items);
    renderMarkers(data.items);
}

function updateStats(data) {
    const stats = document.getElementById("stats");
    stats.innerHTML = `
        <div>Toplam kayıt: <strong>${data.total_count}</strong></div>
        <div>Haritada gösterilen: <strong>${data.map_count}</strong></div>
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
            <a href="${item.source?.url || "#"}" target="_blank">Habere Git</a>
        `;

        newsList.appendChild(card);
    });
}

function clearMarkers() {
    markers.forEach((marker) => marker.setMap(null));
    markers = [];
}

function renderMarkers(items) {
    clearMarkers();

    const bounds = new google.maps.LatLngBounds();
    let hasMarker = false;

    items.forEach((item) => {
        const lat = item.coordinates?.lat;
        const lng = item.coordinates?.lng;

        if (lat === null || lng === null || lat === undefined || lng === undefined) {
            return;
        }

        const position = { lat: Number(lat), lng: Number(lng) };

        const marker = new google.maps.Marker({
            position,
            map,
            title: item.title,
            icon: markerIcons[item.news_type] || undefined,
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
            infoWindow.open(map, marker);
        });

        markers.push(marker);
        bounds.extend(position);
        hasMarker = true;
    });

    if (hasMarker) {
        map.fitBounds(bounds);
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
