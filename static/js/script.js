const config = [
  { id: "gender", label: "Jenis Kelamin", type: "select", options: [{val: 0, text: "Perempuan"}, {val: 1, text: "Laki-laki"}], val: 1 },
  { id: "age", label: "Umur", min: 18, max: 70, val: 28, unit: "thn" },
  { id: "weight", label: "Berat", min: 45, max: 120, val: 65, unit: "kg" },
  { id: "duration", label: "Durasi", min: 30, max: 150, val: 60, step: 1, unit: "menit" },
  { id: "bpm", label: "Detak Jantung", min: 60, max: 200, val: 130, unit: "bpm" }
];

// Bobot telah dipindah ke app.py (Backend)

function init() {
  const container = document.getElementById("controls");
  container.innerHTML = ""; 
  config.forEach(c => {
    if(c.type === "select") {
      container.innerHTML += `
        <div class="space-y-2">
          <label class="text-slate-300 font-medium text-sm">${c.label}</label>
          <select id="${c.id}" class="w-full bg-slate-800 text-white rounded-lg p-3 border border-slate-700 focus:border-rose-500 outline-none transition-all">
            ${c.options.map(opt => `<option value="${opt.val}">${opt.text}</option>`).join('')}
          </select>
        </div>`;
    } else {
      container.innerHTML += `
        <div class="space-y-2">
          <div class="flex justify-between text-sm">
            <label class="text-slate-300 font-medium">${c.label}</label>
            <span class="text-rose-400 font-bold font-mono" id="${c.id}-val">${formatDurationDisplay(c.val, c.id)}</span>
          </div>
          <input type="range" id="${c.id}" min="${c.min}" max="${c.max}" step="${c.step || 1}" value="${c.val}" 
            class="w-full h-1.5 bg-slate-800 rounded-lg appearance-none cursor-pointer"
            oninput="updateValueDisplay('${c.id}', this.value)">
        </div>`;
    }
  });
  renderChart();
}

function formatDurationDisplay(val, id) {
  if (id === 'duration') {
    const hours = Math.floor(val / 60);
    const mins = val % 60;
    if (hours > 0) {
      return `${hours} jam ${mins > 0 ? mins + ' mnt' : ''}`;
    }
    return `${mins} menit`;
  }
  const item = config.find(c => c.id === id);
  return `${val} ${item.unit || ''}`;
}

function updateValueDisplay(id, val) {
  document.getElementById(id + "-val").textContent = formatDurationDisplay(val, id);
}

function startPrediction() {
  const btn = document.getElementById("predict-btn");
  const btnText = document.getElementById("btn-text");
  
  btn.disabled = true;
  btnText.textContent = "Menghubungi Server...";
  btn.classList.add("opacity-70");

  setTimeout(() => {
    calculate();
  }, 500); // Sedikit delay untuk efek UI
}

async function calculate() {
  const gender = parseFloat(document.getElementById("gender").value);
  const age = parseFloat(document.getElementById("age").value);
  const weight = parseFloat(document.getElementById("weight").value);
  const durationTotalMinutes = parseFloat(document.getElementById("duration").value);
  const bpm = parseFloat(document.getElementById("bpm").value);

  try {
    // Meminta hasil perhitungan ke Backend Flask
    const response = await fetch('/predict', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        gender: gender,
        age: age,
        weight: weight,
        duration: durationTotalMinutes,
        bpm: bpm
      })
    });

    if (response.status === 401) {
      alert("Sesi Anda telah berakhir. Anda akan diarahkan ke halaman login.");
      window.location.href = '/login';
      return;
    }

    const data = await response.json();

    if (data.status === 'success') {
      const resultValue = data.predicted_calories;
      animateValue("prediction-value", 0, resultValue, 500);
      
      // Update tampilan durasi di area hasil
      document.getElementById("duration-text").textContent = formatDurationDisplay(durationTotalMinutes, 'duration');
      document.getElementById("duration-bar").style.width = `${((durationTotalMinutes - 30) / 120) * 100}%`;

      updateRecommendation(bpm, durationTotalMinutes);
      
      // Tambahkan ke tabel riwayat secara dinamis
      if (data.new_entry) {
        const tableBody = document.getElementById("history-table-body");
        const noHistoryRow = document.getElementById("no-history-row");
        if (noHistoryRow) {
          noHistoryRow.remove();
        }
        
        const entry = data.new_entry;
        const newRowHTML = `
          <tr class="hover:bg-slate-900/30 transition-all opacity-0" style="transition: opacity 0.5s ease-in-out;">
            <td class="py-3 px-4 font-mono text-xs">${entry.timestamp}</td>
            <td class="py-3 px-4">${entry.gender}</td>
            <td class="py-3 px-4">${entry.age} thn</td>
            <td class="py-3 px-4">${entry.weight} kg</td>
            <td class="py-3 px-4">${entry.duration} mnt</td>
            <td class="py-3 px-4">${entry.bpm} bpm</td>
            <td class="py-3 px-4 font-bold text-white">${entry.predicted_calories} kcal</td>
          </tr>
        `;
        tableBody.insertAdjacentHTML('afterbegin', newRowHTML);
        
        // Efek fade-in halus
        const newRow = tableBody.firstElementChild;
        setTimeout(() => {
          newRow.classList.remove("opacity-0");
        }, 50);
      }
      
      // Kembalikan tombol ke keadaan semula
      const btn = document.getElementById("predict-btn");
      const btnText = document.getElementById("btn-text");
      btn.disabled = false;
      btnText.textContent = "Prediksi Sekarang";
      btn.classList.remove("opacity-70");
      document.getElementById("result-area").scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else {
      console.error("Error dari server:", data.message);
      alert("Gagal melakukan prediksi: " + data.message);
      resetButton();
    }
  } catch (error) {
    console.error("Error:", error);
    alert("Koneksi ke server gagal. Pastikan Flask berjalan.");
    resetButton();
  }
}

function resetButton() {
  const btn = document.getElementById("predict-btn");
  const btnText = document.getElementById("btn-text");
  btn.disabled = false;
  btnText.textContent = "Coba Lagi";
  btn.classList.remove("opacity-70");
}

function animateValue(id, start, end, duration) {
    const obj = document.getElementById(id);
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

function updateRecommendation(bpm, duration) {
  let type = ""; let icon = ""; let desc = "";
  if (bpm >= 160) {
    type = "HIIT / Sprint"; icon = "⚡"; desc = "Intensitas sangat tinggi. Cocok untuk lari cepat.";
  } else if (bpm >= 135) {
    type = "Lari (Running)"; icon = "🏃"; desc = "Zona cardio aktif. Sangat efektif membakar kalori.";
  } else if (bpm >= 115) {
    type = "Lari Santai (Jogging)"; icon = "👟"; desc = "Bagus untuk stamina jangka panjang.";
  } else if (bpm >= 90) {
    type = "Berjalan Cepat"; icon = "🚶‍♂️"; desc = "Olahraga low-impact yang aman untuk sendi.";
  } else {
    type = "Berjalan Santai / Yoga"; icon = "🧘"; desc = "Fokus pada pemulihan dan fleksibilitas.";
  }
  document.getElementById("rec-type").textContent = type;
  document.getElementById("rec-icon").textContent = icon;
  document.getElementById("rec-desc").textContent = desc;
}

function renderChart() {
  const ctx = document.getElementById("typeChart").getContext("2d");
  if(window.myChart) window.myChart.destroy();
  window.myChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['Strength', 'Cardio', 'Yoga', 'HIIT'],
      datasets: [{
        label: 'Distribusi Data',
        data: [258, 255, 239, 221],
        backgroundColor: 'rgba(244, 63, 94, 0.6)',
        borderColor: '#f43f5e',
        borderWidth: 1,
        borderRadius: 5
      }]
    },
    options: {
      indexAxis: 'y',
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { display: false }, ticks: { color: '#64748b' } },
        y: { grid: { display: false }, ticks: { color: '#64748b' } }
      }
    }
  });
}

window.onload = init;
