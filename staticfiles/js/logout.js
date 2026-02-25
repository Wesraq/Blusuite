/**
 * EMS Logout Handler
 * Handles client-side logout and clears all stored user data
 */

function handleLogout() {
    // Clear localStorage
    localStorage.clear();

    // Clear sessionStorage
    sessionStorage.clear();

    // Clear any cookies related to the application
    clearApplicationCookies();

    // Clear browser cache for sensitive data (if supported)
    if ('caches' in window) {
        clearApplicationCache();
    }

    // Add CSRF token to the logout request for security
    const csrfToken = getCSRFToken();

    // Create a form to submit logout with CSRF protection
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/logout/';

    if (csrfToken) {
        const csrfInput = document.createElement('input');
        csrfInput.type = 'hidden';
        csrfInput.name = 'csrfmiddlewaretoken';
        csrfInput.value = csrfToken;
        form.appendChild(csrfInput);
    }

    document.body.appendChild(form);
    form.submit();
}

function clearApplicationCookies() {
    // Get all cookies
    const cookies = document.cookie.split(';');

    cookies.forEach(cookie => {
        const eqPos = cookie.indexOf('=');
        const name = eqPos > -1 ? cookie.substr(0, eqPos).trim() : cookie.trim();

        // Clear cookies that might contain user data
        if (name.includes('sessionid') ||
            name.includes('csrftoken') ||
            name.includes('user') ||
            name.includes('role')) {
            document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
        }
    });
}

function clearApplicationCache() {
    // Clear service worker caches if they exist
    caches.keys().then(names => {
        names.forEach(name => {
            if (name.includes('ems') || name.includes('user') || name.includes('session')) {
                caches.delete(name);
            }
        });
    });
}

function getCSRFToken() {
    // Try to get CSRF token from cookies
    const name = 'csrftoken=';
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(';');

    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) === 0) {
            return c.substring(name.length, c.length);
        }
    }

    // Try to get from meta tag
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.getAttribute('content');
    }

    return null;
}

// Add event listeners when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add logout functionality to all logout buttons/links
    const logoutElements = document.querySelectorAll('.logout-btn, [href*="/logout/"], .sign-out');

    logoutElements.forEach(element => {
        element.addEventListener('click', function(e) {
            e.preventDefault();
            handleLogout();
        });
    });

    // Add logout functionality to forms with logout action
    const logoutForms = document.querySelectorAll('form[action*="/logout/"]');
    logoutForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            handleLogout();
        });
    });

    // Refresh navbar on page load to ensure correct role-based visibility
    setTimeout(() => {
        refreshNavbar();
    }, 100);
});

// Global logout function that can be called from anywhere
window.logout = handleLogout;

// Function to update navbar based on user role
function updateNavbarForRole(userRole, permissions) {
    console.log('=== UPDATING NAVBAR FOR ROLE ===');
    console.log('User Role:', userRole);
    console.log('Permissions:', permissions);

    // Hide/show navbar items based on role
    const navbar = document.querySelector('.nav-menu');
    if (!navbar) {
        console.log('Navbar not found, skipping update');
        return;
    }

    // Remove all existing role-based visibility
    const navItems = navbar.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        item.style.display = 'block'; // Show all by default
    });

    // Apply role-based visibility
    if (userRole === 'EMPLOYEE') {
        // Hide admin-specific items for employees
        hideNavItemByText(navbar, 'Employees');
        hideNavItemByText(navbar, 'Reports');
        console.log('Applied EMPLOYEE navbar restrictions');
    } else if (userRole === 'EMPLOYER_ADMIN' || userRole === 'ADMINISTRATOR') {
        // Show all items for employer admins
        console.log('Applied EMPLOYER_ADMIN navbar permissions');
    } else if (userRole === 'SUPERADMIN') {
        // Show all items for superadmins
        console.log('Applied SUPERADMIN navbar permissions');
    }

    console.log('=== NAVBAR UPDATE COMPLETE ===');
}

// Helper function to hide navbar items by text content
function hideNavItemByText(navbar, text) {
    const navLinks = navbar.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        if (link.textContent.trim().includes(text)) {
            link.closest('.nav-item').style.display = 'none';
        }
    });
}

// Function to refresh navbar from server (for role changes)
function refreshNavbar() {
    console.log('=== REFRESHING NAVBAR FROM SERVER ===');

    // Make an AJAX call to get current user info
    fetch('/api/v1/auth/users/me/', {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Token ${getAuthToken()}`
        }
    })
    .then(response => response.json())
    .then(data => {
        console.log('Server user data:', data);
        updateNavbarForRole(data.role, data);
    })
    .catch(error => {
        console.error('Error refreshing navbar:', error);
    });
}

// Function to get auth token from cookies or localStorage
function getAuthToken() {
    // Try to get from cookies first
    const name = 'token=';
    const decodedCookie = decodeURIComponent(document.cookie);
    const ca = decodedCookie.split(';');

    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') {
            c = c.substring(1);
        }
        if (c.indexOf(name) === 0) {
            return c.substring(name.length, c.length);
        }
    }

    // Try localStorage
    return localStorage.getItem('auth_token') || localStorage.getItem('token');
}
