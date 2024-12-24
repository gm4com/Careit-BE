
/////////////////
// 컨펌 모달 처리
/////////////////

$('button[data-target="#confirm-modal"]').on('click', function (e) {
	var $this = $(this);
	var $modal = $('#confirm-modal');
	$modal.find('.modal-title').text($this.data('title'));
	$modal.find('.modal-body .row .col-12 p').text($this.data('content'));
	$modal.find('.modal-footer .btn-modal-confirm').data('link', $this.data('link'));
	$modal.find('.modal-footer .btn-modal-confirm').text($this.data('btn-text'))
		.removeClass('btn-danger btn-success btn-primary btn-info')
		.addClass('btn-' + $this.data('btn-class'));
});

$('.confirm.modal .btn-modal-confirm').on('click', function (e) {
	e.preventDefault();
	$(this).html('<i class="fa fa-spin fa-spinner"></i> ' + $(this).html());
	$(this).prop('disabled', true);
	var link = $(this).data('link');
	if (link !== undefined && link.length > 0) location.href = link;
	else {
		var $form = $('.confirm.modal form');
		var post = $(this).data('post');
		if (post !== undefined && post.length > 0) $form.prop('action', post).prop('method', 'post');
		$form.submit();
	}
});
