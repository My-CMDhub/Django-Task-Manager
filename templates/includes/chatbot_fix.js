// Chatbot resize functionality fix
(function() {
    // Wait for the DOM to be fully loaded
    document.addEventListener('DOMContentLoaded', function() {
        // Try to find the chatbot elements
        const chatMessages = document.getElementById('chatMessages');
        const toggleSizeBtn = document.getElementById('toggleChatSizeBtn');
        
        // If the elements don't exist, exit early
        if (!chatMessages || !toggleSizeBtn) {
            console.log('Chatbot elements not found, skipping resize fix');
            return;
        }
        
        console.log('Applying chatbot resize fix');
        
        // Define heights
        const defaultHeight = 400;
        const expandedHeight = 800;
        const collapsedHeight = 200;
        
        // Track state
        let isExpanded = false;
        
        // Remove any existing event listeners (if possible)
        toggleSizeBtn.removeEventListener('click', handleToggleClick);
        
        // Define the click handler
        function handleToggleClick(e) {
            // Prevent default behavior and stop propagation
            e.preventDefault();
            e.stopPropagation();
            
            console.log('Chatbot toggle button clicked');
            
            // Toggle state
            isExpanded = !isExpanded;
            
            if (isExpanded) {
                // Force expanded height with !important to override conflicting styles
                chatMessages.style.cssText = `height: ${expandedHeight}px !important; transition: height 0.3s ease !important;`;
                toggleSizeBtn.innerHTML = '<i class="bi bi-arrows-angle-contract"></i>';
                toggleSizeBtn.title = "Collapse";
                console.log('Expanded chat window to', expandedHeight + 'px');
            } else {
                // Force collapsed height with !important to override conflicting styles
                chatMessages.style.cssText = `height: ${collapsedHeight}px !important; transition: height 0.3s ease !important;`;
                toggleSizeBtn.innerHTML = '<i class="bi bi-arrows-angle-expand"></i>';
                toggleSizeBtn.title = "Expand";
                console.log('Collapsed chat window to', collapsedHeight + 'px');
            }
            
            // Scroll to bottom after resize with delay for transition
            setTimeout(function() {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 300);
        }
        
        // Add the click handler
        toggleSizeBtn.addEventListener('click', handleToggleClick);
        
        // Make sure the button is visible and styled properly
        toggleSizeBtn.style.cursor = 'pointer';
        toggleSizeBtn.style.zIndex = '1000';
        toggleSizeBtn.style.position = 'relative';
        
        console.log('Chatbot resize fix applied successfully');
    });
})(); 