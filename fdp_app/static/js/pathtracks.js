(function () {
    "use strict";
    var ctx = window.FDP_CONTEXT;
    var rtRadios = document.querySelectorAll('input[name="reimbursement_type"]');
    var taxiSection = document.getElementById("taxi-section");
    var amountPreview = document.getElementById("amount-preview");
    var tripsInput = document.getElementById("number_of_trips");
    var taxiList = document.getElementById("taxi-amounts-list");

    function isFuel() {
        var c = document.querySelector('input[name="reimbursement_type"]:checked');
        return c && c.value === "CARBURANTE";
    }

    function recompute() {
        var trips = parseInt(tripsInput.value, 10);
        if (!trips || trips < 1) { amountPreview.textContent = "€ -"; return; }
        var amount;
        if (isFuel()) {
            if (!ctx.rate) { amountPreview.textContent = "(rate non configurato)"; return; }
            amount = (ctx.roadKm * 2 * trips) / ctx.rate.km_l * ctx.rate.eur_l;
        } else {
            var inputs = taxiList.querySelectorAll('input[name="taxi_amount"]');
            amount = 0;
            for (var i = 0; i < inputs.length; i++) {
                var v = parseFloat(inputs[i].value);
                if (!isNaN(v)) amount += v;
            }
        }
        amountPreview.textContent = "€ " + amount.toFixed(2);
    }

    function toggleTaxiSection() {
        taxiSection.style.display = isFuel() ? "none" : "block";
        recompute();
    }

    for (var i = 0; i < rtRadios.length; i++) {
        rtRadios[i].addEventListener("change", toggleTaxiSection);
    }
    tripsInput.addEventListener("input", recompute);
    taxiList.addEventListener("input", function (e) {
        if (e.target.name === "taxi_amount") recompute();
    });

    document.getElementById("add-taxi-amount").addEventListener("click", function () {
        var input = document.createElement("input");
        input.type = "number";
        input.className = "form-control mb-2";
        input.name = "taxi_amount";
        input.step = "0.01";
        input.min = "0";
        input.placeholder = "es. 8.30";
        taxiList.appendChild(input);
    });

    toggleTaxiSection();
}());
