from typing import List, Optional, Dict
from sqlmodel import Session, select, func
from .model import Component


def create_component(session: Session, component: Component) -> Component:
    """Create a new component record."""
    session.add(component)
    session.commit()
    session.refresh(component)
    return component


def get_components_by_path(session: Session, component_path: str) -> List[Component]:
    """Get all versions of a component, ordered by created_at desc."""
    statement = (
        select(Component)
        .where(Component.component_path == component_path)
        .order_by(Component.created_at.desc())
    )
    return list(session.exec(statement).all())


def get_component_by_path_and_version(session: Session, component_path: str, version: str) -> Optional[Component]:
    """Get a specific component version."""
    statement = (
        select(Component)
        .where(Component.component_path == component_path, Component.version == version)
    )
    return session.exec(statement).first()


def get_latest_component(session: Session, component_path: str) -> Optional[Component]:
    """Get the most recent version of a component."""
    statement = (
        select(Component)
        .where(Component.component_path == component_path)
        .order_by(Component.created_at.desc())
        .limit(1)
    )
    return session.exec(statement).first()


def component_version_exists(session: Session, component_path: str, version: str, folder: str) -> bool:
    """Check if a component version already exists (matches unique constraint)."""
    statement = select(Component).where(
        Component.folder == folder,
        Component.component_path == component_path,
        Component.version == version
    )
    return session.exec(statement).first() is not None


def get_all_component_paths(session: Session) -> List[str]:
    """Get all unique component paths."""
    statement = select(Component.component_path).distinct()
    return list(session.exec(statement).all())


def get_component_stats(session: Session) -> Dict[str, int]:
    """Get statistics about stored components."""
    total_components = session.exec(select(func.count(Component.id))).first() or 0
    unique_paths = session.exec(select(func.count(Component.component_path.distinct()))).first() or 0
    
    return {
        "unique_components": unique_paths,
        "total_versions": total_components,
        "avg_versions_per_component": total_components / unique_paths if unique_paths > 0 else 0
    }