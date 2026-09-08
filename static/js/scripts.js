// Custom JavaScript can be added here if needed
document.addEventListener('DOMContentLoaded', function() {
    // Enable tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Confirm before deleting
    var deleteButtons = document.querySelectorAll('.delete-btn');
    deleteButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            if (!confirm('Are you sure you want to delete this record?')) {
                e.preventDefault();
            }
        });
    });
    
    // Dynamic form behavior
    var prisonerClassSelect = document.getElementById('id_prisoner_class');
    if (prisonerClassSelect) {
        prisonerClassSelect.addEventListener('change', function() {
            // You can add dynamic form behavior here
        });
    }
});

// static/js/scripts.js
$(document).ready(function() {
    // Initialize date pickers for all date inputs
    $('input[type="date"]').each(function() {
        $(this).datepicker({
            format: 'yyyy-mm-dd',
            autoclose: true,
            todayHighlight: true
        });
    });

    // Log for debugging
    console.log('Date pickers initialized');
});