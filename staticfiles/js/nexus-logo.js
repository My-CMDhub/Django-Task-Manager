/**
 * Nexus Interactive Logo
 * Provides premium interactive tilt and animations for the Nexus logo
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log("Nexus logo script loaded");
    // Only run on devices with hover capability (non-touch)
    const hasHover = window.matchMedia('(hover: hover)').matches;
    const logoElements = document.querySelectorAll('.nexus-logo');
    
    console.log("Found logo elements:", logoElements.length);
    
    logoElements.forEach(logo => {
        const inner = logo.querySelector('.nexus-logo-inner');
        
        // Handle hover/focus events for flip animation
        logo.addEventListener('mouseenter', () => {
            console.log("Mouse enter on logo");
            logo.classList.add('flipped');
        });
        
        logo.addEventListener('mouseleave', () => {
            console.log("Mouse leave on logo");
            logo.classList.remove('flipped');
            // Reset tilt transform
            if (inner) {
                inner.style.transform = '';
            }
        });
        
        // Mirror the hover effects for keyboard focus
        logo.addEventListener('focus', () => {
            console.log("Focus on logo");
            logo.classList.add('flipped');
        });
        
        logo.addEventListener('blur', () => {
            console.log("Blur on logo");
            logo.classList.remove('flipped');
            // Reset tilt transform
            if (inner) {
                inner.style.transform = '';
            }
        });
        
        // Only add tilt effect on devices with hover capability
        if (hasHover && inner) {
            logo.addEventListener('mousemove', (e) => {
                // Get position of mouse relative to the logo
                const rect = logo.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;
                
                // Calculate distance from center as a percentage
                const percentX = (e.clientX - centerX) / (rect.width / 2);
                const percentY = (e.clientY - centerY) / (rect.height / 2);
                
                // Calculate rotation (max ±15 degrees)
                const rotateY = percentX * 15;
                const rotateX = percentY * -15; // Negative to make it follow the mouse naturally
                
                // Apply tilt transform with GPU acceleration
                inner.style.transform = `rotateY(${rotateY}deg) rotateX(${rotateX}deg)`;
            });
        }
    });
}); 