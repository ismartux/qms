from django import template

register = template.Library()

@register.filter
def attachment_url(attachment):
    """
    Generate the correct URL for an attachment (old SubmissionAttachment or new SubmissionImage).
    
    Usage:
        <img src="{{ att|attachment_url }}" ...>
    """
    # Check if it's a SubmissionImage (new model with BinaryField)
    if hasattr(attachment, 'image') and hasattr(attachment, 'id') and not hasattr(attachment, 'file'):
        # New SubmissionImage model - use the API endpoint
        return f"/api/image/{attachment.id}/"
    
    # Old SubmissionAttachment model - use the file.url
    if hasattr(attachment, 'file') and attachment.file:
        return attachment.file.url
    
    return "#"

@register.filter
def is_submission_image(attachment):
    """Check if attachment is a SubmissionImage (new model)"""
    return hasattr(attachment, 'image') and hasattr(attachment, 'id') and not hasattr(attachment, 'file')