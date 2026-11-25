/** Khung xương (skeleton) thay cho chữ "Đang tải": giữ đúng bố cục để trang không giật khi dữ liệu về. */

export function MenuSkeleton({ cards = 6 }: { cards?: number }) {
	return (
		<div className="qo-grid" aria-busy="true" aria-label="Đang tải menu">
			{Array.from({ length: cards }, (_, i) => (
				<div key={i} className="qo-card qo-card--skel" aria-hidden="true">
					<span className="qo-skel qo-card__media" />
					<span className="qo-card__body">
						<span className="qo-skel qo-skel--line" />
						<span className="qo-skel qo-skel--line qo-skel--short" />
					</span>
				</div>
			))}
		</div>
	);
}

/** Màn đầu trong lúc chờ get_shop: banner + thương hiệu + 2 ô nhập. */
export function PageSkeleton() {
	return (
		<main className="qo-login" aria-busy="true" aria-label="Đang tải">
			<span className="qo-skel qo-skel--hero" aria-hidden="true" />
			<div className="qo-login__body" aria-hidden="true">
				<div className="qo-skel-brand">
					<span className="qo-skel qo-skel--logo" />
					<span className="qo-skel-brand__text">
						<span className="qo-skel qo-skel--line" />
						<span className="qo-skel qo-skel--line qo-skel--short" />
					</span>
				</div>
				<span className="qo-skel qo-skel--title" />
				<span className="qo-skel qo-skel--input" />
				<span className="qo-skel qo-skel--input" />
				<span className="qo-skel qo-skel--input" />
			</div>
		</main>
	);
}
