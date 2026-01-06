import { Link, useParams } from 'react-router-dom';

export default function DashboardPicker({ dashboards, onNew, onEdit, isEditing }) {
  const { dashboardId } = useParams();
  const dashboardList = Object.values(dashboards);

  return (
    <div className="dashboard-picker">
      <div className="dashboard-tabs">
        {dashboardList.map((db) => (
          <Link
            key={db.id}
            to={`/dashboards/${db.id}`}
            className={`dashboard-tab ${dashboardId === db.id ? 'active' : ''}`}
          >
            {db.name}
          </Link>
        ))}
        <button
          type="button"
          className="dashboard-tab dashboard-tab--new"
          onClick={onNew}
        >
          + New
        </button>
        {dashboardId && (
          <button
            type="button"
            className={`dashboard-tab dashboard-tab--edit ${isEditing ? 'active' : ''}`}
            onClick={onEdit}
          >
            {isEditing ? 'Cancel Edit' : 'Edit'}
          </button>
        )}
      </div>
    </div>
  );
}
