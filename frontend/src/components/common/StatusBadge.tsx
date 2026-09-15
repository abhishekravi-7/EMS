import React from 'react';

interface StatusBadgeProps {
  status: string;
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  let badgeClass = 'badge ';

  switch (status) {
    case 'ACTIVE':
    case 'PRESENT':
    case 'PAID':
      badgeClass += 'badge-active';
      break;
    case 'INACTIVE':
    case 'ABSENT':
    case 'PENDING':
      badgeClass += 'badge-inactive';
      break;
    case 'ON_LEAVE':
    case 'HALF_DAY':
    case 'LATE':
      badgeClass += 'badge-leave';
      break;
    default:
      badgeClass += 'badge-active';
      break;
  }

  return (
    <span className={badgeClass}>
      {status}
    </span>
  );
};

export default StatusBadge;
