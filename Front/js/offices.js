document.addEventListener("DOMContentLoaded", () => {
    const searchForm = document.getElementById("search-form");
    const resultsContent = document.getElementById("results-content");
    const resultsCount = document.getElementById("results-count");

    searchForm.addEventListener("submit", async function (e) {
        e.preventDefault();

        const address = document.getElementById("search-query").value.trim();
        if (!address) {
            resultsContent.innerHTML = `
                <div class="no-results">
                    <i class="fas fa-map-marker-alt"></i>
                    <h3>Please enter an address</h3>
                    <p>E.g. "Bratislava, Nivy" or "Košice, Old Town"</p>
                </div>
            `;
            resultsCount.textContent = "Found: 0 centers";
            return;
        }

        resultsContent.innerHTML = `
            <div class="no-results">
                <i class="fas fa-spinner fa-spin"></i>
                <h3>Searching...</h3>
            </div>
        `;

        try {
            const response = await fetch("/api/offices/nearby", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    address: address,
                    ui_language: "en"
                })
            });

            const data = await response.json();

            if (data.status !== "success") {
                throw new Error("Server returned an error");
            }

            const offices = data.data.offices;

            if (!offices || offices.length === 0) {
                resultsContent.innerHTML = `
                    <div class="no-results">
                        <i class="fas fa-info-circle"></i>
                        <h3>No nearby centers found</h3>
                        <p>Try a bigger city or another location</p>
                    </div>
                `;
                resultsCount.textContent = "Found: 0 centers";
                return;
            }

            let html = `
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>Center</th>
                            <th>Address</th>
                            <th>Contacts</th>
                            <th>Distance</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            offices.forEach(o => {
                html += `
                    <tr>
                        <td>
                            <div class="form-name">${o.name}</div>
                            <div class="form-country">${o.city}, ${o.country}</div>
                        </td>
                        <td>${o.address}</td>
                        <td>
                            ${o.phone || ""}
                            <br>${o.email || ""}
                            ${o.website ? `<br><a href="${o.website}" target="_blank">Website</a>` : ""}
                        </td>
                        <td>${o.distance_km_estimate !== null ? o.distance_km_estimate + " km" : "-"}</td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                </table>
            `;

            resultsContent.innerHTML = html;
            resultsCount.textContent = `Found: ${offices.length} centers`;

        } catch (err) {
            resultsContent.innerHTML = `
                <div class="no-results">
                    <i class="fas fa-exclamation-triangle"></i>
                    <h3>Error</h3>
                    <p>${err.message}</p>
                </div>
            `;
            resultsCount.textContent = "Found: 0 centers";
        }
    });
});
