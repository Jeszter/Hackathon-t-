function loadComponents() {
    return fetch('../components/header.html')
        .then(response => {
            if (!response.ok) throw new Error('Header not found');
            return response.text();
        })
        .then(data => {
            document.body.insertAdjacentHTML('afterbegin', data);
            highlightCurrentPage();
            initHeaderEvents();

            // TRANSLATE HEADER AFTER LOADING
            if (typeof translatePage === 'function') {
                translatePage();
            }
        })
        .catch(error => console.error('Error loading header:', error));
}

function loadFooter() {
    return fetch('/footer.html')
        .then(response => {
            if (!response.ok) throw new Error('Footer not found');
            return response.text();
        })
        .then(data => {
            document.body.insertAdjacentHTML('beforeend', data);

            // TRANSLATE FOOTER AFTER LOADING
            if (typeof translatePage === 'function') {
                translatePage();
            }
        })
        .catch(error => console.error('Error loading footer:', error));
}

function highlightCurrentPage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        link.classList.remove('active');
        const linkHref = link.getAttribute('href');

        if (currentPath === linkHref ||
            (currentPath === '/' && linkHref === '/')) {
            link.classList.add('active');
        }
    });
}

function initHeaderEvents() {
    const languageBtn = document.getElementById('languageBtn');
    const languageDropdown = document.getElementById('languageDropdown');

    if (languageBtn && languageDropdown) {
        languageBtn.addEventListener('click', function() {
            languageDropdown.style.display =
                languageDropdown.style.display === 'block' ? 'none' : 'block';
        });

        document.addEventListener('click', function(event) {
            if (!event.target.closest('.language-switcher')) {
                languageDropdown.style.display = 'none';
            }
        });

        const languageOptions = document.querySelectorAll('.language-option');
        languageOptions.forEach(option => {
            option.addEventListener('click', function() {
                const lang = this.getAttribute('data-lang');
                if (typeof setLanguage === 'function') {
                    setLanguage(lang);
                }
                languageDropdown.style.display = 'none';
            });
        });
    }
}

document.addEventListener('DOMContentLoaded', function() {
    Promise.all([loadComponents(), loadFooter()])
        .then(() => {
            console.log('All components loaded successfully');
        })
        .catch(error => {
            console.error('Error loading components:', error);
        });
});