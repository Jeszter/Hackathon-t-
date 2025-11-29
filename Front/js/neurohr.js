// Элементы DOM
const fileInput = document.getElementById('cvFile');
const fileName = document.getElementById('fileName');
const analyzeBtn = document.getElementById('analyzeBtn');
const uploadArea = document.getElementById('uploadArea');
const resultsSection = document.getElementById('resultsSection');

// Обработчик выбора файла
fileInput.addEventListener('change', function() {
    if (this.files && this.files[0]) {
        const file = this.files[0];
        fileName.textContent = file.name;
        analyzeBtn.disabled = false;
        uploadArea.classList.add('active');
    } else {
        fileName.textContent = 'No file selected';
        analyzeBtn.disabled = true;
        uploadArea.classList.remove('active');
    }
});

// Drag and drop функциональность
uploadArea.addEventListener('dragover', function(e) {
    e.preventDefault();
    uploadArea.classList.add('active');
});

uploadArea.addEventListener('dragleave', function() {
    uploadArea.classList.remove('active');
});

uploadArea.addEventListener('drop', function(e) {
    e.preventDefault();
    uploadArea.classList.remove('active');

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        fileInput.files = e.dataTransfer.files;
        const file = e.dataTransfer.files[0];
        fileName.textContent = file.name;
        analyzeBtn.disabled = false;
    }
});

// Обработчик анализа CV
analyzeBtn.addEventListener('click', function() {
    // Имитация процесса анализа
    analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
    analyzeBtn.disabled = true;

    setTimeout(function() {
        // Показываем результаты
        resultsSection.style.display = 'block';
        analyzeBtn.innerHTML = 'Analyze My CV';
        analyzeBtn.disabled = false;

        // Прокрутка к результатам
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }, 2000);
});

// Обработчик для мобильного меню
document.querySelector('.mobile-menu-btn').addEventListener('click', function() {
    const navMenu = document.querySelector('.nav-menu');
    navMenu.classList.toggle('active');

    // Смена иконки меню
    const icon = this.querySelector('i');
    if (navMenu.classList.contains('active')) {
        icon.classList.remove('fa-bars');
        icon.classList.add('fa-times');
    } else {
        icon.classList.remove('fa-times');
        icon.classList.add('fa-bars');
    }
});

// Плавная прокрутка
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const targetId = this.getAttribute('href');
        if (targetId === '#') return;

        const targetElement = document.querySelector(targetId);
        if (targetElement) {
            window.scrollTo({
                top: targetElement.offsetTop - 80,
                behavior: 'smooth'
            });

            // Закрытие мобильного меню после клика
            document.querySelector('.nav-menu').classList.remove('active');
        }
    });
});