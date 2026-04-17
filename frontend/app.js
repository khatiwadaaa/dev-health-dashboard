// frontend/app.js
angular.module("devHealthApp", [])
  .controller("DashboardController", ["$http", "$timeout", function($http, $timeout) {
    var vm = this;
    var API = "http://localhost:3000/api";

    vm.owner   = "";
    vm.repo    = "";
    vm.result  = null;
    vm.cve     = null;
    vm.loading = false;
    vm.error   = "";
    vm.allScans = [];

    // Load previous scans on startup
    $http.get(API + "/scans").then(function(res) {
      vm.allScans = res.data;
    });

    // Trigger analysis
    vm.analyze = function() {
      if (!vm.owner || !vm.repo) {
        vm.error = "Please enter both owner and repo.";
        return;
      }
      vm.loading = true;
      vm.error   = "";
      vm.result  = null;
      vm.cve     = null;

      $http.post(API + "/analyze", { owner: vm.owner, repo: vm.repo })
        .then(function(res) {
          vm.result = res.data;
          vm.loading = false;
          $timeout(function() { renderCharts(vm.result); }, 100);
          loadCVE(vm.owner, vm.repo);
          $http.get(API + "/scans").then(function(r) { vm.allScans = r.data; });
        })
        .catch(function(err) {
          vm.error   = "Analysis failed. Is the Node.js server running?";
          vm.loading = false;
        });
    };

    // Load a previous scan from MySQL
    vm.loadScan = function(owner, repo) {
      vm.loading = true;
      $http.get(API + "/scans/" + owner + "/" + repo)
        .then(function(res) {
          vm.result  = res.data.raw_json;
          vm.owner   = owner;
          vm.repo    = repo;
          vm.loading = false;
          $timeout(function() { renderCharts(vm.result); }, 100);
          loadCVE(owner, repo);
        });
    };

    // Color class based on score
    vm.scoreClass = function(score) {
      if (score >= 75) return "score-good";
      if (score >= 50) return "score-ok";
      return "score-bad";
    };

    function loadCVE(owner, repo) {
      $http.get(API + "/cve/" + owner + "/" + repo)
        .then(function(res) { vm.cve = res.data; });
    }

    function renderCharts(data) {
      // Language doughnut chart
      var langCtx = document.getElementById("langChart");
      if (langCtx && data.languages) {
        if (window._langChart) window._langChart.destroy();
        var langs  = Object.keys(data.languages);
        var bytes  = Object.values(data.languages);
        window._langChart = new Chart(langCtx, {
          type: "doughnut",
          data: {
            labels: langs,
            datasets: [{ data: bytes,
              backgroundColor: ["#378ADD","#1D9E75","#EF9F27","#D85A30","#7F77DD","#D4537E"] }]
          },
          options: { plugins: { legend: { position: "bottom" } } }
        });
      }

      // Weekly trend line chart
      var trendCtx = document.getElementById("trendChart");
      if (trendCtx && data.commits && data.commits.weekly_trend) {
        if (window._trendChart) window._trendChart.destroy();
        var trend   = data.commits.weekly_trend;
        window._trendChart = new Chart(trendCtx, {
          type: "line",
          data: {
            labels: trend.map(function(t) { return t.week; }),
            datasets: [{
              label: "Commits",
              data:  trend.map(function(t) { return t.commits; }),
              borderColor: "#378ADD",
              backgroundColor: "rgba(55,138,221,0.08)",
              tension: 0.3,
              fill: true
            }]
          },
          options: {
            scales: { y: { beginAtZero: true } },
            plugins: { legend: { display: false } }
          }
        });
      }
    }
  }]);
