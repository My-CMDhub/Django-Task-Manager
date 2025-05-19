/**
 * Nexus Interactive Logo
 * Provides premium interactive tilt and animations for the Nexus logo
 */
document.addEventListener('DOMContentLoaded', function() {
    // Only run on devices with hover capability (non-touch)
    const hasHover = window.matchMedia('(hover: hover)').matches;
    const logoElements = document.querySelectorAll('.nexus-logo');
    
    logoElements.forEach(logo => {
        const inner = logo.querySelector('.nexus-logo-inner');
        
        // Handle hover/focus events for flip animation
        logo.addEventListener('mouseenter', () => {
            logo.classList.add('flipped');
        });
        
        logo.addEventListener('mouseleave', () => {
            logo.classList.remove('flipped');
            // Reset tilt transform
            if (inner) {
                inner.style.transform = 'rotateY(0deg) rotateX(0deg)';
            }
        });
        
        // Mirror the hover effects for keyboard focus
        logo.addEventListener('focus', () => {
            logo.classList.add('flipped');
        });
        
        logo.addEventListener('blur', () => {
            logo.classList.remove('flipped');
            // Reset tilt transform
            if (inner) {
                inner.style.transform = 'rotateY(0deg) rotateX(0deg)';
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